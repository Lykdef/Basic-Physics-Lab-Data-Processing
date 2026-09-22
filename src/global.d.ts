export {};
declare global {
  interface Window { labDesktop?: { calculate: (payload:unknown) => Promise<unknown>; openProject: () => Promise<string | null>; saveProject: (name: string, content: string) => Promise<boolean> } }
}
