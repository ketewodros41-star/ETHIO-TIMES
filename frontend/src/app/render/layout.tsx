// No nav/header/footer for the Playwright render route
export default function RenderLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
