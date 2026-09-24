using System;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Diagnostics;
using System.Drawing;
using System.Security.Cryptography;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;
using Microsoft.Win32;

// BuildConfig is generated from the actual release archive; hashes are embedded.
class Installer : Form {
    Label status = new Label { Left=24, Top=28, Width=470, Height=64, Text="正在准备安装物理实验室…" };
    ProgressBar progress = new ProgressBar { Left=24, Top=102, Width=470, Height=20 };
    Button retry = new Button { Left=394, Top=146, Width=100, Text="重试", Visible=false };
    readonly string root = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "PhysicalLab", "versions");
    readonly string[] args;
    bool busy;
    WebClient client;
    public Installer(string[] arguments) {
        args=arguments; Text="物理实验室安装程序 " + BuildConfig.Version;
        ClientSize=new Size(520,190); FormBorderStyle=FormBorderStyle.FixedDialog; MaximizeBox=false;
        StartPosition=FormStartPosition.CenterScreen; Font=new Font("Microsoft YaHei",10);
        Controls.AddRange(new Control[]{status,progress,retry});
        Shown += async (s,e)=>await Install(); retry.Click += async (s,e)=>await Install();
        FormClosing += (s,e)=>{if(busy){e.Cancel=true;status.Text="正在安装，请等待完成；网络下载可稍后重试。";}};
    }
    async Task Download(string url,string file) {
        using(client=new WebClient()) {
            client.Headers.Add("User-Agent","PhysicalLab-Installer");
            client.DownloadProgressChanged += (s,e)=>{progress.Value=Math.Max(0,Math.Min(100,e.ProgressPercentage));status.Text=String.Format("下载运行环境：{0:F1} MB / {1:F1} MB",e.BytesReceived/1000000.0,e.TotalBytesToReceive/1000000.0);};
            var job=client.DownloadFileTaskAsync(new Uri(url),file);
            if(await Task.WhenAny(job,Task.Delay(TimeSpan.FromMinutes(15)))!=job){client.CancelAsync();throw new Exception("下载超时，请检查网络后重试。");}
            await job;
        }
    }
    static bool HasWebView() {
        foreach(var hive in new[]{RegistryHive.LocalMachine,RegistryHive.CurrentUser})
        foreach(var view in new[]{RegistryView.Registry32,RegistryView.Registry64})
        using(var key=RegistryKey.OpenBaseKey(hive,view))
        using(var clients=key.OpenSubKey(@"SOFTWARE\Microsoft\EdgeUpdate\Clients")) {
            if(clients==null)continue;
            foreach(var name in clients.GetSubKeyNames())using(var item=clients.OpenSubKey(name)) {
                string label=Convert.ToString(item.GetValue("name")),version=Convert.ToString(item.GetValue("pv"));
                if(label.IndexOf("WebView2",StringComparison.OrdinalIgnoreCase)>=0 && !String.IsNullOrEmpty(version) && version!="0.0.0.0")return true;
            }
        }
        return false;
    }
    static void Extract(string zip,string target) {
        using(var archive=ZipFile.OpenRead(zip))foreach(var entry in archive.Entries) {
            string destination=Path.GetFullPath(Path.Combine(target,entry.FullName));
            if(!destination.StartsWith(Path.GetFullPath(target)+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))throw new Exception("压缩包路径无效");
            if(String.IsNullOrEmpty(entry.Name)){Directory.CreateDirectory(destination);continue;}
            Directory.CreateDirectory(Path.GetDirectoryName(destination));entry.ExtractToFile(destination);
        }
    }
    void Shortcuts(string executable) {
        Type type=Type.GetTypeFromProgID("WScript.Shell");
        dynamic shell=Activator.CreateInstance(type);
        foreach(string folder in new[]{Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory),Environment.GetFolderPath(Environment.SpecialFolder.Programs)}) {
            dynamic shortcut=shell.CreateShortcut(Path.Combine(folder,"物理实验室.lnk"));
            shortcut.TargetPath=executable;shortcut.WorkingDirectory=Path.GetDirectoryName(executable);shortcut.Save();
        }
    }
    async Task Install() {
        busy=true;retry.Visible=false;string staging=null;
        bool test=args.Length==2 && args[0]=="--verify-package";
        bool installOnly=args.Length==1 && args[0]=="--install-only";
        try {
            ServicePointManager.SecurityProtocol=SecurityProtocolType.Tls12;
            string installRoot=test?Path.Combine(Path.GetDirectoryName(Path.GetFullPath(args[1])),"installer-verification"):root;
            Directory.CreateDirectory(installRoot);
            string target=Path.Combine(installRoot,BuildConfig.Version),exe=Path.Combine(target,"PhysicalLab.exe");
            if(!File.Exists(exe) || !File.Exists(Path.Combine(target,".complete"))) {
                staging=Path.Combine(installRoot,"download-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(staging);
                string archive=Path.Combine(staging,"runtime.zip");
                if(test)File.Copy(args[1],archive);else await Download(BuildConfig.Url,archive);
                status.Text="正在校验运行环境…";
                string hash;using(var stream=File.OpenRead(archive))using(var sha=SHA256.Create())hash=BitConverter.ToString(sha.ComputeHash(stream)).Replace("-","").ToLowerInvariant();
                if(hash!=BuildConfig.Hash)throw new Exception("下载校验失败，请重试。");
                status.Text="正在安装运行环境…";
                string unpack=Path.Combine(staging,"unpacked");Directory.CreateDirectory(unpack);
                await Task.Run(()=>Extract(archive,unpack));
                string payload=Path.Combine(unpack,BuildConfig.Folder);
                if(!File.Exists(Path.Combine(payload,"PhysicalLab.exe")))throw new Exception("安装包缺少主程序");
                File.WriteAllText(Path.Combine(payload,".complete"),hash);
                if(Directory.Exists(target))Directory.Move(target,target+".incomplete-"+Guid.NewGuid().ToString("N"));
                Directory.Move(payload,target);
            }
            if(!test && !HasWebView()) {
                status.Text="正在安装 Microsoft WebView2…";
                if(staging==null){staging=Path.Combine(installRoot,"download-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(staging);}
                string webview=Path.Combine(staging,"WebView2Setup.exe");
                await Download("https://go.microsoft.com/fwlink/p/?LinkId=2124703",webview);
                var process=Process.Start(new ProcessStartInfo(webview,"/silent /install"){UseShellExecute=false,CreateNoWindow=true});
                bool finished=await Task.Run(()=>process.WaitForExit(600000));
                if(!finished || !HasWebView())throw new Exception("WebView2 安装未完成，请检查网络后重试。");
            }
            if(!test){Shortcuts(exe);if(!installOnly)Process.Start(new ProcessStartInfo(exe){WorkingDirectory=target,UseShellExecute=true});}
            busy=false;Environment.ExitCode=0;Close();
        } catch(Exception error) {
            Environment.ExitCode=1;status.Text="安装失败："+error.Message;retry.Visible=true;
            if(test || installOnly){busy=false;Close();}
        } finally {
            busy=false;
            if(staging!=null && Directory.Exists(staging))try{Directory.Delete(staging,true);}catch{}
        }
    }
    [STAThread] static void Main(string[] args) {
        bool created;
        using(var mutex=new Mutex(true,"Local\\PhysicalLab-Installer-"+BuildConfig.Version,out created)) {
            if(!created){MessageBox.Show("安装程序已经运行。","物理实验室");return;}
            Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);Application.Run(new Installer(args));
        }
    }
}
