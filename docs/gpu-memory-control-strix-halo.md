# Control de memoria GPU en AMD Strix Halo desde Linux sin tocar el BIOS

**Si es posible controlar cuanta memoria ve la GPU desde Linux**, pero con matices importantes. El mecanismo correcto en kernels modernos (6.14+) es `ttm.pages_limit`, que reemplaza al deprecado `amdgpu.gttsize`. Este parametro ajusta el tamano del pool GTT (Graphics Translation Table) -- la memoria de sistema que la GPU puede mapear dinamicamente -- y es la via principal para maximizar la memoria GPU-accesible en arquitecturas UMA como Strix Halo. Todos los cambios requieren reinicio; no existe reconfiguracion en caliente. AMD recomienda oficialmente fijar el BIOS en **512 MB de VRAM** y expandir GTT via TTM, ya que en UMA no hay diferencia de rendimiento entre VRAM "carved-out" y GTT.

---

## 1. Parametros del modulo amdgpu para controlar memoria

El driver `amdgpu` expone varios parametros de modulo relacionados con memoria, pero el control real del pool GPU en sistemas UMA recae en el subsistema TTM:

| Parametro | Funcion | Estado |
|-----------|---------|--------|
| `ttm.pages_limit` | **Maximo de paginas 4KiB mapeables por la GPU** | Metodo actual correcto |
| `ttm.page_pool_size` | Paginas pre-reservadas en pool WC/UC/DMA | Activo (opcional) |
| `amdgpu.gttsize` | Tamano GTT en MiB | **Deprecado desde kernel 6.14+** |
| `amdgpu.vramlimit` | Restringe VRAM total (solo reduce, no aumenta) | Activo (testing) |
| `amdgpu.vis_vramlimit` | Restringe VRAM visible por CPU | Activo (testing) |
| `amdgpu.gartsize` | Tamano GART (uso del kernel, no userspace) | Activo |
| `amdgpu.vm_fragment_size` | Tamano de fragmento VM en bits | Activo |

**Distincion critica entre namespaces TTM**: dependiendo del driver kernel, el modulo se llama `ttm` o `amdttm`. Con Ubuntu 24.04 y kernel upstream 6.17/6.18, el modulo correcto es **`ttm`** (no `amdttm`). El prefijo `amdttm.*` solo aplica a sistemas con el driver DKMS de AMD Instinct y **se ignora silenciosamente** en Strix Halo con kernels upstream. Verificar con:

```bash
ls /sys/module/ttm/parameters/ 2>/dev/null && echo "Usar ttm.*" || echo "Usar amdttm.*"
```

**Formula de conversion** (el valor se expresa en paginas de 4 KiB):
```
paginas = GB_deseados x 262144
```

Valores de referencia para 128 GB de sistema:

| GB para GPU | Valor `pages_limit` | Nota |
|-------------|---------------------|------|
| 96 GB | 25,165,824 | Conservador |
| 108 GB | 27,648,000 | Balance recomendado |
| 120 GB | 31,457,280 | Agresivo |
| 124 GB | 32,505,856 | Maximo practico (kyuz0 toolboxes) |

---

## 2. `amdgpu.gttsize` en gfx1151: funcional pero oficialmente deprecado

El parametro `amdgpu.gttsize` **todavia funciona** en Strix Halo pero esta **oficialmente deprecado desde kernel 6.14+**. El parche fue introducido por Mario Limonciello (AMD) y el kernel emite esta advertencia en dmesg:

```
amdgpu: [drm] Configuring gttsize via module parameter is deprecated, please use ttm.pages_limit
```

El problema real es mas sutil: **usar solo `gttsize` sin `ttm.pages_limit` causa un desacople peligroso**. El driver reporta el tamano GTT configurado en dmesg, pero el subsistema TTM no necesariamente reserva esa memoria. Resultado tipico de esta inconsistencia:

```
GTT size has been set as 103079215104 but TTM size has been set as 48956567552, this is unusual
```

Esto significa que dmesg muestra 96 GB de GTT "ready", pero ROCm solo puede acceder a ~45 GB reales. Por eso el proyecto kyuz0/amd-strix-halo-toolboxes usa **ambos parametros simultaneamente** como medida de compatibilidad: `amdgpu.gttsize=126976 ttm.pages_limit=32505856`.

**Cuidado con el typo**: `amdgpu.gtt_size` (con guion bajo) es un parametro **desconocido que se ignora silenciosamente** -- el correcto es `amdgpu.gttsize` sin guion bajo. Este error documentado en ROCm issue #5595 causo que varios usuarios solo vieran 62 GB en lugar de los 96 GB configurados.

---

## 3. `ttm.pages_limit`: el mecanismo correcto y como configurarlo

`ttm.pages_limit` establece el **numero maximo de paginas de 4 KiB** que el Translation Table Manager puede asignar para uso GPU. Este es el parametro que realmente controla cuanta memoria del sistema puede mapear la GPU en su espacio de direcciones virtuales.

### Configuracion via GRUB (metodo recomendado)

```bash
# Editar GRUB
sudo nano /etc/default/grub

# Anadir a GRUB_CMDLINE_LINUX_DEFAULT:
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash iommu=pt ttm.pages_limit=32505856 ttm.page_pool_size=32505856"

# Aplicar y reiniciar
sudo update-grub && sudo reboot
```

### Configuracion via modprobe.d (alternativa)

```bash
# Crear /etc/modprobe.d/ttm.conf
echo "options ttm pages_limit=32505856" | sudo tee /etc/modprobe.d/ttm.conf
echo "options ttm page_pool_size=32505856" | sudo tee -a /etc/modprobe.d/ttm.conf

# Regenerar initramfs (importante si ttm se carga desde initramfs)
sudo update-initramfs -u
sudo reboot
```

### Configuracion via herramienta oficial `amd-ttm`

AMD proporciona una utilidad CLI que simplifica el proceso:

```bash
sudo apt install pipx
pipx ensurepath
pipx install amd-debug-tools

# Consultar configuracion actual:
amd-ttm
# Current TTM pages limit: 16469033 pages (62.82 GB)
# Total system memory: 125.65 GB

# Configurar 108 GB:
amd-ttm --set 108
# Successfully set TTM pages limit to 28311552 pages (108.00 GB)
# Configuration written to /etc/modprobe.d/ttm.conf

# Revertir:
amd-ttm --clear
```

La herramienta escribe en `/etc/modprobe.d/ttm.conf` y requiere reinicio. **Advertencia**: en kernels 6.17+ el `amd-ttm` tool puede necesitar actualizacion para detectar correctamente si usar el namespace `ttm` vs `amdttm` (issue ROCm #5562).

### Diferencia entre `pages_limit` y `page_pool_size`

**`pages_limit`** define el techo maximo de paginas asignables -- es el limite duro. **`page_pool_size`** define cuantas paginas se pre-reservan en el pool de cache WC/UC/DMA -- estas paginas quedan **permanentemente indisponibles para el sistema operativo**. Si solo ejecutas cargas AI dedicadas, igualar ambos valores maximiza rendimiento. Si el sistema es multiproposito, puedes fijar `page_pool_size` mas bajo o no fijarlo (dejando que sea dinamico), y solo establecer `pages_limit`.

---

## 4. Reconfiguracion en caliente: no es posible

**No existe ningun metodo para cambiar la asignacion VRAM/GTT en caliente en Strix Halo.** Todas las vias requieren reinicio:

- Los parametros TTM (`pages_limit`, `page_pool_size`) se fijan al cargar el modulo del kernel y los ficheros sysfs correspondientes son **solo lectura** en runtime.
- El modulo `amdgpu` no puede descargarse/recargarse porque es el driver de display activo.
- La herramienta `amd-ttm --set` escribe en modprobe.d y requiere reinicio explicito.
- La nueva interfaz sysfs `uma/carveout` (en proceso de upstream por AMD) permite cambiar el carve-out del BIOS desde Linux, pero el cambio **solo surte efecto en el siguiente arranque**.

El driver si asigna memoria GTT **dinamicamente dentro del limite configurado** -- es decir, una aplicacion puede pedir 80 GB y luego liberarlos sin reiniciar. Lo que no se puede cambiar en caliente es el **limite maximo** del pool.

---

## 5. BIOS 512 MB + GTT grande vs BIOS 64 GB fijo

| Aspecto | BIOS 64 GB VRAM fija | BIOS 512 MB + GTT 124 GB |
|---------|---------------------|--------------------------|
| RAM disponible para el SO | **64 GB** (la otra mitad reservada permanentemente) | **~127.5 GB** (solo 512 MB reservados, el resto compartido dinamicamente) |
| Memoria GPU maxima accesible | 64 GB VRAM + GTT adicional | 512 MB VRAM + hasta 124 GB GTT |
| Rendimiento GPU | Identico (UMA = misma DRAM fisica) | Identico |
| Herramientas de monitoreo | nvtop/btop muestran 64 GB VRAM | nvtop/btop muestran solo 512 MB (confuso pero correcto) |
| Carga de modelos LLM >64 GB | Problemas reportados con mmap | Funciona sin restricciones con `--no-mmap` |
| Flexibilidad | Nula -- SO siempre pierde 64 GB | Maxima -- memoria se comparte dinamicamente |

**AMD recomienda explicitamente** el enfoque de BIOS minimo + GTT grande. La documentacion oficial de ROCm para Strix Halo indica: *"Keep BIOS VRAM reservation small and increase the shared TTM/GTT limit instead."* En UMA no hay distincion de rendimiento entre VRAM carved-out y GTT, ya que ambas acceden a la misma DRAM fisica con el mismo controlador de memoria.

El commit `torvalds/linux@759e764` es clave aqui: cuando GTT > VRAM, el driver amdgpu usa **GTT-backed allocations** para el dominio VRAM de forma transparente. Esto significa que incluso aplicaciones que piden "VRAM" reciben memoria GTT sin penalizacion.

**Recomendacion**: Cambiar el BIOS de 64 GB fijos a 512 MB y configurar `ttm.pages_limit=32505856` (124 GB). Recuperas ~63.5 GB de RAM para el SO manteniendo mas memoria accesible por la GPU.

---

## 6. Proyectos y herramientas de la comunidad

- **kyuz0/amd-strix-halo-toolboxes** (1,100+ estrellas): Contenedores Docker/Toolbx pre-configurados con ROCm 6.4.4, 7.2 y nightlies. Incluye `gguf-vram-estimator.py`, `run_distributed_llama.py`. Config referencia: Fedora 42/43, kernel 6.18.6, firmware linux-firmware-20260110, `iommu=pt amdgpu.gttsize=126976 ttm.pages_limit=32505856`.

- **lhl/strix-halo-testing** (213 estrellas): Benchmarks LLM en Framework Desktop. Config optimizada con `amd_iommu=off` (6% mas rapido) y perfil `tuned accelerator-performance` (+5-8% en prompt processing).

- **AMD amd-debug-tools** (oficial): Paquete pip con la herramienta `amd-ttm`. Instalable via `pipx install amd-debug-tools`.

- **Gygeek/Framework-strix-halo-llm-setup**: Guia setup Ubuntu para ROCm + llama.cpp en Strix Halo.

- **strixhalo.wiki**: Wiki comunitaria con calculadora de limites de memoria.

- **ROCm/TheRock**: Builds nightly de ROCm optimizados para gfx1151.

---

## 7. Que reportan `rocminfo` y `rocm-smi` segun la configuracion

### Con BIOS 96 GB VRAM (sin parametros TTM, kernel 6.16.9+):
```
# rocminfo
Pool 1: GLOBAL; FLAGS: COARSE GRAINED    Size: 100663296(0x6000000) KB  # ~96 GB
Pool 2: GLOBAL; FLAGS: EXTENDED FINE GRAINED  Size: 100663296 KB

# rocm-smi
GPU[0] : VRAM Total Memory (B): 103079215104   # 96 GB
GPU[0] : GTT Total Memory (B): 16633114624      # ~15.5 GB (default residual)
```

### Con BIOS 512 MB + `ttm.pages_limit=32505856` (124 GB GTT):
```
# rocminfo
Pool 1: GLOBAL; FLAGS: COARSE GRAINED    Size: ~130023424 KB  # ~124 GB
Pool 2: GLOBAL; FLAGS: EXTENDED FINE GRAINED  Size: ~130023424 KB

# rocm-smi
GPU[0] : VRAM Total Memory (B): 536870912       # 512 MB
GPU[0] : GTT Total Memory (B): 133143986176     # ~124 GB

# dmesg
[drm] amdgpu: 512M of VRAM memory ready
[drm] amdgpu: 126976M of GTT memory ready
```

### Bugs conocidos en reporting

- En kernels < 6.16.9, ROCm solo veia ~15.5 GB independientemente de la configuracion (bug ROCm #5444, resuelto).
- rocm-smi puede mostrar integer underflow en VRAM usage (~18.4 exabytes) en ciertas configuraciones (bug ROCm #5750).
- nvtop y btop reportan solo la VRAM del BIOS (ej. 512 MB) e ignoran GTT -- confuso pero esperado.
- vulkaninfo reporta correctamente VRAM + GTT como memoria total del dispositivo.

---

## 8. Ficheros sysfs para leer y escribir memoria

### Ficheros de lectura (siempre disponibles):

```bash
# Bajo /sys/class/drm/card0/device/ (o card1, segun el sistema):
mem_info_vram_total      # VRAM total en bytes (carved-out del BIOS)
mem_info_vram_used       # VRAM en uso en bytes
mem_info_vis_vram_total  # VRAM visible por CPU en bytes (= vram_total en APU)
mem_info_vis_vram_used   # VRAM visible en uso
mem_info_gtt_total       # GTT total en bytes
mem_info_gtt_used        # GTT en uso en bytes

# Parametros TTM actuales:
/sys/module/ttm/parameters/pages_limit       # Limite actual de paginas
/sys/module/ttm/parameters/page_pool_size    # Tamano del pool de paginas
/sys/module/ttm/parameters/dma32_pages_limit # Limite DMA32

# Parametro legacy:
/sys/module/amdgpu/parameters/gttsize        # Valor configurado de gttsize
```

### Interfaz UMA carveout (nueva, en proceso de upstream):

En kernels con los parches de Yo-Jung Leo Lin y Mario Limonciello (AMD), aparecen ficheros adicionales si el BIOS soporta la funcion ATCS 0xA:

```bash
# Leer opciones disponibles:
cat /sys/class/drm/card0/device/uma/carveout_options
# 0: Minimum (512 MB)
# 1: (1 GB)
# 2: (2 GB)
# ...
# 9: High (32 GB)

# Leer configuracion actual:
cat /sys/class/drm/card0/device/uma/carveout

# Escribir nueva configuracion (surte efecto en el PROXIMO arranque):
echo 0 > /sys/class/drm/card0/device/uma/carveout
```

Esta interfaz permite cambiar el carve-out del BIOS sin entrar al BIOS, pero requiere soporte del firmware y solo surte efecto tras reinicio.

### Script de verificacion rapida:

```bash
#!/bin/bash
echo "=== Strix Halo Memory Status ==="
echo "Kernel: $(uname -r)"
echo "VRAM total: $(echo "scale=1; $(cat /sys/class/drm/card*/device/mem_info_vram_total | head -1) / 1073741824" | bc) GB"
echo "VRAM usado: $(echo "scale=1; $(cat /sys/class/drm/card*/device/mem_info_vram_used | head -1) / 1073741824" | bc) GB"
echo "GTT total:  $(echo "scale=1; $(cat /sys/class/drm/card*/device/mem_info_gtt_total | head -1) / 1073741824" | bc) GB"
echo "GTT usado:  $(echo "scale=1; $(cat /sys/class/drm/card*/device/mem_info_gtt_used | head -1) / 1073741824" | bc) GB"
echo "TTM pages_limit: $(cat /sys/module/ttm/parameters/pages_limit 2>/dev/null || echo 'N/A') paginas"
echo "TTM pool_size:   $(cat /sys/module/ttm/parameters/page_pool_size 2>/dev/null || echo 'N/A') paginas"
echo "Cmdline: $(cat /proc/cmdline)"
```

---

## Configuracion recomendada para el sistema

Para Ryzen AI MAX+ 395 con 128 GB, Ubuntu 24.04, kernel 6.18+ y ROCm 7.2:

**Paso 1 -- BIOS**: Cambiar UMA/VRAM de 64 GB a **512 MB** (minimo). Habilitar Resizable BAR si disponible.
- Ruta tipica GMKtec EVO-X2: `Advanced > AMD CBS > GFX Configuration > UMA Frame Buffer Size > 512M`

**Paso 2 -- GRUB** (`/etc/default/grub`):
```bash
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash iommu=pt ttm.pages_limit=32505856 ttm.page_pool_size=32505856"
```

**Paso 3 -- Aplicar y reiniciar**:
```bash
sudo update-grub && sudo reboot
```

**Paso 4 -- Verificar**:
```bash
cat /sys/module/ttm/parameters/pages_limit   # Debe mostrar 32505856
cat /sys/class/drm/card*/device/mem_info_gtt_total  # Debe mostrar ~133143986176
sudo dmesg | grep "amdgpu.*memory"  # Debe mostrar "512M of VRAM" + "126976M of GTT"
```

**Parametros adicionales opcionales**: `amdgpu.cwsr_enable=0` (estabilidad con ROCm), `amd_iommu=off` (6% mas rendimiento en memoria, pero desactiva visibilidad del NPU). Para llama.cpp, usar siempre `-fa 1 --no-mmap`. Evitar **linux-firmware-20251125** (rompe ROCm en Strix Halo) -- usar firmware 20260110 o posterior.

**Nota sobre kernel 6.16.9+**: Con este kernel y BIOS en 96 GB, ROCm detecta automaticamente los 96 GB sin necesidad de parametros TTM adicionales. Sin embargo, con BIOS en 512 MB + TTM configurado se obtiene mayor flexibilidad y mas RAM disponible para el SO, que es la configuracion que AMD recomienda oficialmente.

---

## Respuesta directa: BIOS a 512 MB

512 MB es lo minimo y es lo correcto. No 1 GB.

El BIOS VRAM en Strix Halo no es la memoria que usa la GPU para IA. Es solo un pequeno "carveout" permanente necesario para:
- Arrancar la pantalla antes de que Linux cargue
- El framebuffer del display
- Algunas estructuras de bajo nivel del driver

Para eso, 512 MB sobra. La GPU carga los modelos de IA (8 GB, 28 GB, lo que sea) a traves del GTT dinamico -- esa es la memoria real de trabajo, controlada desde GRUB con `ttm.pages_limit`.

Poner 1 GB en vez de 512 MB solo significa perder 512 MB extra de RAM para el OS sin ningun beneficio.
