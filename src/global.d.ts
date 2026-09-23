export {};
declare global {
  interface Window {
    labInitialWorkspace?:string|null;
    pywebview?:{api:{calculate:(payload:unknown)=>Promise<unknown>;open_project:()=>Promise<string|null>;save_project:(name:string,content:string)=>Promise<boolean>;load_workspace:()=>Promise<string|null>;save_workspace:(content:string)=>Promise<boolean>}};
    labDesktop?: { calculate: (payload:unknown) => Promise<unknown>; openProject: () => Promise<string | null>; saveProject: (name: string, content: string) => Promise<boolean>;saveWorkspace?:(content:string)=>Promise<void> }
  }
}
