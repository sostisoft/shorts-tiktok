# Optimización de ROCm en Strix Halo: diagnóstico y solución completa

Tu configuración tiene **un error crítico de arquitectura** que probablemente causa la mayor parte de los problemas: estás usando `HSA_OVERRIDE_GFX_VERSION=11.0.0` (gfx1100 = Navi 31, RX 7900 XTX discreto), pero el Ryzen AI MAX+ 395 es **gfx1151** (RDNA 3.5). gfx1100 y gfx1151 difieren en subsistema de memoria, wave size y paths de optimización. Además, el kernel 6.17 **no cumple el requisito mínimo** de AMD para Strix Halo (6.18.4+), y es casi seguro que `enable_model_cpu_offload()` está provocando thrashing SVM masivo en una arquitectura UMA donde las copias entre "CPU" y "GPU" son redundantes. La combinación de estos tres factores explica los 6 minutos de inferencia, los errores de SVM, y las muertes de proceso.

Lo que sigue es el análisis técnico detallado de cada pregunta, con recomendaciones concretas basadas en documentación oficial de AMD, issues de GitHub, parches del kernel, y configuraciones validadas por la comunidad.

---

## 1. pipe.to("cuda") es la única opción correcta en UMA

En una arquitectura UMA como Strix Halo, donde VRAM y RAM son físicamente el mismo pool de LPDDR5X, **`enable_model_cpu_offload()` provoca thrashing SVM innecesario y destruye el rendimiento**. PyTorch no tiene consciencia de UMA — esto está confirmado por tres issues abiertos en el repositorio de PyTorch (issues #145693, #107605, #100656) que documentan explícitamente que "memcpy ops become redundant" en UMA pero PyTorch no los evita.

Lo que realmente ocurre bajo el capó: cuando diffusers llama `.to("cuda")`, PyTorch ejecuta `hipMalloc()` + `hipMemcpy(HostToDevice)`. Cuando llama `.to("cpu")`, ejecuta `hipMemcpy(DeviceToHost)` + `hipFree()`. En una GPU discreta esto mueve datos por PCIe. En Strix Halo **no hay PCIe**, pero el runtime igualmente realiza copias reales entre pools de memoria con distintas propiedades de coherencia: `hipMalloc` asigna desde el pool **coarse-grained** (no coherente, GPU puede cachear agresivamente — óptimo para ML), mientras que la memoria CPU usa el pool **fine-grained** (coherente, con overhead de protocolo de coherencia). Aunque la DRAM es la misma, **las copias son reales** y se miden a ~58 GB/s en benchmarks de MI300A, no son instantáneas. Cada copia implica remapeo de page tables, flush de caches y actualizaciones de SVM ranges.

`enable_model_cpu_offload()` de diffusers usa hooks de HuggingFace Accelerate: carga componentes enteros (text encoder ~2-5GB, transformer ~12-20GB, VAE ~2-5GB) a CUDA cuando se ejecuta su `forward()`, y los descarga a CPU cuando el siguiente componente empieza. Para un modelo de difusión haciendo 20-50 pasos de denoising, esto genera **decenas de ciclos de hipMalloc/hipMemcpy/hipFree por imagen**, cada uno manipulando page tables del SVM manager — exactamente los `svm_range_restore_work` que saturan tu CPU.

**Recomendación definitiva**: usa exclusivamente `pipe.to("cuda")`. Un modelo de 24GB (FLUX.1-schnell) o 28GB (Wan2.1) cabe holgadamente en 64GB de memoria unificada. El cpu_offload fue diseñado para GPUs discretas con VRAM limitada (ej: meter 24GB en una GPU de 12GB). En UMA con VRAM suficiente, **solo añade overhead con zero beneficio**. Cuando cambies entre modelos secuencialmente, haz `del pipe; torch.cuda.empty_cache(); gc.collect()` antes de cargar el siguiente.

---

## 2. Variables de entorno ROCm/HSA: configuración óptima validada

La configuración correcta de variables de entorno para Strix Halo difiere sustancialmente de lo que usas actualmente. Lo más urgente es cambiar el GFX version override.

**`HSA_OVERRIDE_GFX_VERSION=11.5.1`** (NO 11.0.0): gfx1100 es RDNA 3 discreto con wave64 y diferente subsistema de memoria. gfx1151 es RDNA 3.5 APU con wave32. Usar el target incorrecto fuerza paths de optimización equivocados en rocBLAS, MIOpen y los kernels de PyTorch. La comunidad llm-tracker.info documenta que "gfx1100 kernels are currently 2-6x faster than gfx1151 kernels" por regresiones de optimización, pero los desarrolladores de TheRock 7.9+ han resuelto estas regresiones con workarounds. Con TheRock 7.9rc2+ y soporte nativo gfx1151, **ya no necesitas HSA_OVERRIDE_GFX_VERSION en absoluto**.

**`HSA_ENABLE_SDMA=0`** — **Obligatorio en APU UMA**. Los motores SDMA están diseñados para saturar PCIe 4.0 x16 (~32 GB/s). En UMA sin PCIe, SDMA añade overhead innecesario y causa artefactos (checkerboard en VAE decodes) y ring timeouts documentados en ROCR-Runtime issue #180. Al desactivarlo, ROCm usa "blit kernels" — compute kernels que corren en los shader cores de la GPU, que es más eficiente en UMA. Con TheRock 7.11+, AMD ha indicado que este workaround ya no debería ser necesario, pero en ROCm 6.2-7.2 es crítico.

**`GPU_MAX_ALLOC_PERCENT=100` / `GPU_SINGLE_ALLOC_PERCENT=100` / `GPU_MAX_HEAP_SIZE=100`** — La documentación oficial de AMD MI300A explica que ROCm restringe por defecto el porcentaje de GPU que las aplicaciones pueden asignar (herencia de aplicaciones OpenCL que probe-until-fail). Para ML con modelos de 24-28GB, estos límites deben ser 100. AMD advierte que con 100% aumenta el riesgo de OOM del OS, pero con modelos que ocupan <50% de los 64GB disponibles, el riesgo es aceptable.

**`HSA_XNACK`** — **No soportado en gfx1100 ni gfx1151**. En la tabla ISA del ROCR-Runtime, todas las GPUs gfx10xx y gfx11xx tienen xnack como "unsupported". El código del kernel Linux confirma: "GFXv10 and later GPUs do not support shader preemption during page faults." Configurar `HSA_XNACK=1` será silenciosamente ignorado. Algunas guías comunitarias lo incluyen, pero no tiene efecto funcional.

**`HSA_FORCE_FINE_GRAIN_PCIE`** — Diseñado para interconexiones PCIe discretas. En UMA no hay PCIe entre CPU y GPU. La guía de Smithery lo incluye junto con HSA_XNACK como "CRITICAL for accessing full memory", pero esto es guidance comunitaria no validada por AMD. En UMA puede forzar un path de coherencia sub-óptimo. Recomendación: probar con y sin; probablemente no tiene efecto.

**`AMDGPU_NO_DEFAULTTILING`** — No existe en la documentación oficial de ROCm ni en ROCR-Runtime. No aparece en variables de entorno de HIP, HSA ni ROCm. No usar.

**`PYTORCH_HIP_ALLOC_CONF`** — Configurar como `"backend:native,expandable_segments:True,garbage_collection_threshold:0.9"` para mejorar gestión de memoria PyTorch con workloads >32GB. `expandable_segments:True` evita fragmentación interna del allocator de PyTorch.

**Hugepages**: AMD recomienda explícitamente Transparent Huge Pages (THP) para APUs UMA en su documentación de MI300A. THP reduce presión en TLB, frecuencia de page faults SVM, y overhead de page tables para asignaciones grandes de ML. Además, la compactación proactiva es crítica para evitar fragmentación:

```bash
# Variables de entorno completas (contenedor Docker)
export HSA_OVERRIDE_GFX_VERSION=11.5.1    # CORRECTO para gfx1151
export PYTORCH_ROCM_ARCH=gfx1151
export HSA_ENABLE_SDMA=0
export GPU_MAX_ALLOC_PERCENT=100
export GPU_SINGLE_ALLOC_PERCENT=100
export GPU_MAX_HEAP_SIZE=100
export ROCR_VISIBLE_DEVICES=0
export HIP_VISIBLE_DEVICES=0
export HSA_OVERRIDE_CPU_AFFINITY_DEBUG=0
export PYTORCH_HIP_ALLOC_CONF="backend:native,expandable_segments:True,garbage_collection_threshold:0.9"
export AMD_LOG_LEVEL=0

# Host (sysctl)
echo always > /sys/kernel/mm/transparent_hugepage/enabled
echo 20 > /proc/sys/vm/compaction_proactiveness
echo 1 > /proc/sys/vm/compact_unevictable_allowed
echo 0 > /proc/sys/kernel/numa_balancing
```

---

## 3. El split VRAM/RAM de 64GB/64GB es el problema — AMD recomienda VRAM mínima

La documentación oficial de AMD para Strix Halo, publicada el 2026-02-20, es inequívoca: **"AMD recommends keeping the dedicated VRAM reservation in BIOS small (for example 0.5 GB) and increasing the shared (TTM/GTT) limit instead."** La razón es fundamental: "Because memory is physically shared, there is no performance distinction similar to discrete GPUs where dedicated VRAM is significantly faster than system memory. Firmware may optionally reserve some memory exclusively for GPU use, but this provides little benefit for most workloads while **permanently reducing** available system memory."

Tu configuración actual de **64GB VRAM fijos** tiene múltiples problemas graves. Primero, esos 64GB están permanentemente reservados para la GPU y no están disponibles para Linux, Docker, Python ni el sistema operativo. Si tu sistema tiene 64GB totales y 64GB están como VRAM, el OS tiene **0GB de RAM disponible** — esto explica las muertes de proceso sin OOM killer (el KFD del driver amdgpu mata los queues de compute al no poder asignar buffers de gestión). Segundo, el GTT no puede expandirse más allá de la VRAM reservada de forma efectiva, impidiendo la flexibilidad que ROCm necesita.

El comportamiento del GTT en Strix Halo funciona así: GTT define cuánta RAM del sistema puede mapearse en los address spaces virtuales de la GPU para procesos de usuario. Si GTT > VRAM reservada, el driver amdgpu usa "GTT-backed allocations" para VRAM (commit torvalds/linux@759e764). PyTorch y los frameworks de ML **prefieren GTT-backed allocations** porque permiten mapeos grandes y flexibles sin reservar memoria permanentemente.

Para tu sistema de 64GB con modelos de 24-28GB usados secuencialmente, la configuración óptima es:

- **BIOS VRAM**: **512MB** (mínimo posible)
- **TTM/GTT**: **~56-60GB** (dejar 4-8GB para OS/Docker/Python)
- **Kernel params**:
  ```
  ttm.pages_limit=14680064 ttm.page_pool_size=14680064
  ```
  (Cálculo: 56GB × 1024 × 1024 / 4KB = 14,680,064 páginas)

El parámetro legacy `amdgpu.gttsize` está **deprecated** en kernels modernos; usar `ttm.pages_limit` en su lugar. Si usas el driver amdgpu-dkms (no el in-kernel), el prefijo puede ser `amdttm.` en vez de `ttm.`. AMD también proporciona la herramienta `amd-ttm` (pip install amd-debug-tools): `amd-ttm --set 56` configura 56GB de GTT y escribe la configuración en `/etc/modprobe.d/ttm.conf`.

El impacto en el thrashing SVM es directo: con 64GB de VRAM fija y 0GB para el sistema, cada operación que necesita memoria del OS (malloc de Python, buffers de Docker, page tables del kernel) compite con la VRAM asignada. El SVM manager intenta restaurar páginas constantemente porque la memoria está fragmentada entre pools incompatibles. Reducir VRAM a 512MB y expandir GTT a 56GB elimina esta competencia y permite que ROCm gestione la memoria dinámicamente.

Un bug adicional crítico: **kernels anteriores a 6.16.9 tienen un bug donde ROCm solo ve ~15.5GB de VRAM** independientemente de la configuración BIOS (ROCm issue #5444). Si tu kernel 6.17 incluye este fix, verás la VRAM completa, pero si no, PyTorch intentará meter 24GB en 15.5GB — causando exactamente el thrashing que describes.

---

## 4. Parámetros del módulo kernel amdgpu: los críticos para Strix Halo

El parámetro más impactante para Strix Halo es `amdgpu.cwsr_enable=0`, documentado en ROCm issue #5590 como workaround para hangs del firmware MES 0x80 durante workloads de compute. Un segundo issue (#5915) confirma que `cwsr_enable=0` reduce memory leaks del driver amdgpu-dkms de ~90 GB/hr a ~5.4 GB/hr. Este es el workaround más citado en toda la comunidad Strix Halo.

**`amdgpu.cwsr_enable=0`** — CWSR (Compute Wave Save/Restore) permite preemption de shaders mid-wave. En Strix Halo con firmware MES 0x80, causa hangs reproducibles durante CUDA graph capture con modelos grandes. Desactivarlo previene la preemption de compute waves, lo cual es aceptable para workloads de ML dedicados. La documentación del issue #5590 muestra que un usuario de vLLM en Strix Halo con 125GB unified memory reprodujo el hang consistentemente y lo resolvió con este parámetro.

**`amdgpu.noretry`** — Controla el modo retry/no-retry de XNACK en el SQ. Default -1 (auto). Para APUs, el auto-detect típicamente habilita retry. `noretry=0` permite que los GPU page faults triggeren migración on-demand de páginas SVM. `noretry=1` hace que los page faults sean fatales y maten el shader. Para workloads SVM en APU, asegurar `noretry=0` o dejar en default. Nota: como XNACK está marcado "unsupported" en gfx1151, el impacto real de este parámetro puede ser limitado.

**`amdgpu.vm_size`** — Override del tamaño del address space virtual por cliente en GiB. Default -1 (auto, típicamente 256 TiB en GFX11). Con 64GB de memoria, el default es más que suficiente. No necesita ajuste.

**`amdgpu.sched_hw_submission`** — Profundidad del queue de submission de hardware. Default 2. Aumentar a 4 puede mejorar throughput en workloads de compute sostenidos al ocultar latencia de submission. Para inferencia ML con batches grandes, probar con 4.

**`amdgpu.moverate`** — Tasa máxima de migración de buffers en MB/s. **Default extremadamente bajo: 8 MB/s**. Para un sistema UMA de 64GB con modelos de 24-28GB, esto es potencialmente un cuello de botella enorme si hay migraciones SVM. Aumentar a 1024 o superior: `amdgpu.moverate=1024`.

**GFXOFF** — No existe un parámetro `amdgpu.gfxoff_enable` directo en el kernel upstream. GFXOFF se controla via ppfeaturemask o debugfs (`/sys/kernel/debug/dri/0/amdgpu_gfxoff`). El driver ya desactiva GFXOFF automáticamente durante compute en GFX11. Si ves mensajes `amdgpu_device_delay_enable_gfx_off hogged CPU`, desactívalo: `echo 0 > /sys/kernel/debug/dri/0/amdgpu_gfxoff`.

**`amdgpu.ppfeaturemask`** — ROCm issue #5750 documenta que en Strix Halo, **incluso con ppfeaturemask=0xffffffff, los clocks se quedan atascados en idle (~885MHz en vez de 2900MHz max)**. Si tu GPU está a 885MHz durante inferencia, esto solo explica el rendimiento 3x peor de lo esperado. No hay workaround confirmado; es un bug de power management activo.

Configuración completa recomendada:

```bash
# /etc/modprobe.d/amdgpu.conf
options amdgpu cwsr_enable=0 moverate=1024

# /etc/default/grub — GRUB_CMDLINE_LINUX additions:
iommu=pt ttm.pages_limit=14680064 ttm.page_pool_size=14680064 transparent_hugepage=always numa_balancing=disable
```

### Bugs conocidos que afectan tu configuración exacta

El **ROCm issue #5952** es tu caso exacto: "SVM mapping failure during sequential model loads" — reportado en febrero 2026 con kernel 6.17, muestra cientos de `svm_range_restore_work [amdgpu] hogged CPU for >10000us` seguidos de "Freeing queue vital buffer, queue evicted". Testeado en kernels 6.8 a 6.18.7 y ROCm 7.1/7.2/7.3. Es un **bug activo sin resolver** que afecta múltiples arquitecturas GPU. Las causas raíz identificadas en parches de Emily Deng (marzo 2025) incluyen race conditions en page table freeing y checkpoint timestamps del SVM manager.

El issue #6012 documenta que la cascada de queue evictions puede matar el compositor del display después de 30-60 minutos de uso sostenido, y que **3 procesos concurrentes funcionan pero 4+ fallan**. Tu muerte de proceso sin OOM killer es consistente con esta cascada: el KFD destruye los queues de la GPU, matando el proceso sin involucrar al OOM killer de Linux.

**El requisito más urgente es actualizar el kernel a 6.18.4+**. AMD documenta oficialmente que Strix Halo requiere commits específicos en el KFD driver que están en 6.18.4+: "Without these updates, GPU compute workloads may fail to initialize or behave unpredictably." El proyecto kyuz0/amd-strix-halo-toolboxes (1.1k stars) confirma: "Kernels older than 6.18.4 have a bug that causes stability issues on gfx1151." También evitar linux-firmware-20251125 (rompe ROCm en Strix Halo); usar firmware ≥ 20260110.

---

## Plan de acción inmediato ordenado por impacto

Los cambios están priorizados por la probabilidad de resolver tus síntomas específicos. Los tres primeros son casi seguro responsables de la mayoría de tus problemas:

1. **Cambiar a `HSA_OVERRIDE_GFX_VERSION=11.5.1`** (o desinstalar ROCm 6.2 e instalar wheels nativos gfx1151 de TheRock 7.9+, que no necesitan override)
2. **Reemplazar `enable_model_cpu_offload()` por `pipe.to("cuda")`** — elimina el thrashing SVM de copias redundantes
3. **Actualizar kernel a 6.18.4+** (AMD lo marca como requisito, no recomendación)
4. **BIOS**: reducir VRAM a 512MB, configurar `ttm.pages_limit=14680064`
5. **Kernel params**: `amdgpu.cwsr_enable=0 amdgpu.moverate=1024 iommu=pt`
6. **Environment**: `HSA_ENABLE_SDMA=0 GPU_MAX_ALLOC_PERCENT=100`
7. **Host sysctl**: THP=always, compaction_proactiveness=20, numa_balancing=0

Si tu reloj de GPU está atascado en ~885MHz (verificable con `rocm-smi` o `amdgpu_top`), eso es el issue #5750 sin workaround confirmado — pero cambiando a gfx1151 nativo y kernel 6.18.4+ puede resolverse. Como referencia: el propio benchmark de AMD para FLUX.2 FP8 en Ryzen AI Max+ reporta ~6 minutos, indicando que el rendimiento actual de ROCm en Strix Halo para difusión todavía no es comparable a CUDA en RTX 4090 (~10-18s). Pero con la configuración correcta, deberías acercarte al rendimiento que AMD documenta, no estar 10x peor que el ya lento baseline de AMD.

Para ComfyUI específicamente, la comunidad recomienda adicionalmente `--disable-mmap` (el mmap sobre 64GB es muy lento en ROCm actual), `--bf16-vae` (previene OOM en VAE decoding), y `--cache-none` (mejor gestión de memoria unificada). El proyecto ignatberesnev/comfyui-gfx1151 proporciona un Docker validado para este hardware exacto.
