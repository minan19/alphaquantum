/**
 * Faz 4 — /admin/colors panel sayfası.
 *
 * `(app)` route grubu auth gerektirir; sidebar otomatik gelir.
 * Backend `manage_design_tokens` permission ile korunur (admin only).
 */
import { AdminColorsPanel } from "@/components/admin/colors-panel";

export const metadata = { title: "Tasarım Tokenları · Admin" };

export default function Page() {
  return <AdminColorsPanel />;
}
