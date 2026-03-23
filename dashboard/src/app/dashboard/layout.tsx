import { redirect } from "next/navigation";
import { getSession } from "@/lib/auth";
import { Sidebar } from "@/components/layout/sidebar";
import { Header } from "@/components/layout/header";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getSession();

  if (!session.apiKey) {
    redirect("/login");
  }

  return (
    <div className="flex h-screen">
      <Sidebar isAdmin={session.isAdmin} />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header tenantName={session.tenantName} plan={session.plan} />
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
}
