// Native Windows UI. No account/password input: Google sign-in happens in MuMu.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Text;
using System.Web.Script.Serialization;
using System.Windows.Forms;

class AppButton : Button {
    public bool Dark;
    protected override void OnPaint(PaintEventArgs e){
        if(Enabled){base.OnPaint(e);return;}
        e.Graphics.Clear(BackColor);
        using(var pen=new Pen(FlatAppearance.BorderColor))e.Graphics.DrawRectangle(pen,0,0,Width-1,Height-1);
        TextRenderer.DrawText(e.Graphics,Text,Font,ClientRectangle,Dark?Color.FromArgb(156,163,175):Color.FromArgb(115,125,140),TextFormatFlags.HorizontalCenter|TextFormatFlags.VerticalCenter|TextFormatFlags.SingleLine);
    }
}

class AndroidHelper : Form {
    readonly string root=AppDomain.CurrentDomain.BaseDirectory;
    readonly string data=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"AndroidHelper");
    readonly Dictionary<Control,string> labels=new Dictionary<Control,string>();
    readonly List<Button> actions=new List<Button>();
    readonly List<Button> plans=new List<Button>();
    readonly JavaScriptSerializer json=new JavaScriptSerializer();
    Preferences prefs;
    TextBox log; Label status; CheckBox account;
    Button cancel,language,theme;
    Process worker;
    bool ready;
    string statusKey="initial";

    string T(string key){return UiText.Get(key,prefs.English);}
    string SettingsPath{get{return Path.Combine(data,"settings.json");}}
    AndroidHelper() {
        prefs=Preferences.Load(SettingsPath);
        Text="Android Helper";ClientSize=new Size(950,740);MinimumSize=new Size(950,680);
        Font=new Font("Segoe UI",10);StartPosition=FormStartPosition.CenterScreen;
        var layout=new TableLayoutPanel{Dock=DockStyle.Fill,Padding=new Padding(25),ColumnCount=1,RowCount=9};
        foreach(int height in new[]{50,60,52,43,60,58,45})layout.RowStyles.Add(new RowStyle(SizeType.Absolute,height));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent,100));layout.RowStyles.Add(new RowStyle(SizeType.Absolute,49));
        Controls.Add(layout);
        var header=new TableLayoutPanel{Dock=DockStyle.Fill,ColumnCount=2,RowCount=1};
        header.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,70));header.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,30));
        header.Controls.Add(Bind(new Label{Font=new Font("Segoe UI",22,FontStyle.Bold),AutoSize=true},"title"),0,0);
        var options=Row();options.FlowDirection=FlowDirection.RightToLeft;
        theme=Button("",()=>{prefs.Dark=!prefs.Dark;ApplyTheme();ApplyLabels();SavePreferences();});
        language=Button("",()=>{prefs.English=!prefs.English;ApplyLabels();SavePreferences();});
        options.Controls.Add(theme);options.Controls.Add(language);header.Controls.Add(options,1,0);
        layout.Controls.Add(header,0,0);
        layout.Controls.Add(Bind(new Label{Dock=DockStyle.Fill},"intro"),0,1);
        var tools=Row();layout.Controls.Add(tools,0,2);
        Add(tools,"check",()=>Run("check"));Add(tools,"install",()=>Run("play"));
        Add(tools,"offers",()=>Run("list"),true);Add(tools,"login",()=>Run("open-login"));
        account=Bind(new CheckBox{AutoSize=true,Dock=DockStyle.Fill},"account");layout.Controls.Add(account,0,3);
        var steps=Row();layout.Controls.Add(steps,0,4);
        Add(steps,"step1",()=>Purchase("pro12"),true);Add(steps,"step2",()=>Purchase("pro6"),true);
        Add(steps,"step3",()=>Purchase("pro6b"),true);Add(steps,"extra",()=>Purchase("pro6c"),true);
        layout.Controls.Add(Bind(new Label{Dock=DockStyle.Fill},"note"),0,5);
        status=new Label{Dock=DockStyle.Fill,Font=new Font("Segoe UI",11,FontStyle.Bold)};layout.Controls.Add(status,0,6);
        log=new TextBox{Multiline=true,ReadOnly=true,ScrollBars=ScrollBars.Vertical,Dock=DockStyle.Fill,Font=new Font("Consolas",9),BorderStyle=BorderStyle.FixedSingle};
        layout.Controls.Add(log,0,7);
        var bottom=Row();layout.Controls.Add(bottom,0,8);
        Add(bottom,"subscriptions",()=>Run("subscriptions"));Add(bottom,"source",()=>OpenFolder(Path.Combine(root,"src")));
        Add(bottom,"log",()=>OpenFolder(data));Add(bottom,"guide",()=>OpenFile(Path.Combine(root,prefs.English?"START HERE.txt":"НАЧНИТЕ ЗДЕСЬ.txt")));
        cancel=Add(bottom,"stop",Stop);
        Directory.CreateDirectory(data);ApplyLabels();ApplyTheme();UpdateButtons();
        FormClosing+=delegate(object sender,FormClosingEventArgs e){
            if(Busy){if(MessageBox.Show(T("close"),Text,MessageBoxButtons.YesNo,MessageBoxIcon.Question)!=DialogResult.Yes){e.Cancel=true;return;}Stop();}
        };
    }
    bool Busy{get{return worker!=null&&!worker.HasExited;}}
    FlowLayoutPanel Row(){return new FlowLayoutPanel{Dock=DockStyle.Fill,WrapContents=true};}
    C Bind<C>(C control,string key) where C:Control{labels[control]=key;return control;}
    Button Button(string text,Action click){var b=new AppButton{Text=text,AutoSize=true,Padding=new Padding(8,4,8,4),Margin=new Padding(0,3,8,3)};b.Click+=delegate{click();};return b;}
    Button Add(FlowLayoutPanel panel,string key,Action click,bool requiresReady=false){var b=Bind(Button("",click),key);panel.Controls.Add(b);actions.Add(b);if(requiresReady)plans.Add(b);return b;}
    void ApplyLabels(){foreach(var pair in labels)pair.Key.Text=T(pair.Value);theme.Text=T(prefs.Dark?"light":"dark");language.Text=prefs.English?"RU":"EN";if(statusKey!=null)status.Text=T(statusKey);}
    void ApplyTheme(){PaintControls(this);status.ForeColor=prefs.Dark?Color.FromArgb(147,197,253):Color.FromArgb(35,85,155);}
    void PaintControls(Control control){
        control.BackColor=prefs.Dark?Color.FromArgb(17,24,39):Color.FromArgb(245,247,251);
        control.ForeColor=prefs.Dark?Color.FromArgb(229,231,235):Color.FromArgb(25,35,50);
        var box=control as TextBox;if(box!=null)box.BackColor=prefs.Dark?Color.FromArgb(8,15,28):Color.White;
        var button=control as Button;if(button!=null){button.FlatStyle=FlatStyle.Flat;button.UseVisualStyleBackColor=false;button.BackColor=prefs.Dark?Color.FromArgb(31,41,55):Color.White;button.FlatAppearance.BorderColor=prefs.Dark?Color.FromArgb(75,85,99):Color.FromArgb(185,195,210);}
        var themed=control as AppButton;if(themed!=null){themed.Dark=prefs.Dark;themed.Invalidate();}
        foreach(Control child in control.Controls)PaintControls(child);
    }
    void SavePreferences(){try{prefs.Save(SettingsPath);}catch(Exception e){Append(e.Message);}}
    void SetStatus(string key){statusKey=key;status.Text=T(key);}
    void UpdateButtons(){foreach(var b in actions)b.Enabled=!Busy;foreach(var b in plans)b.Enabled=!Busy&&ready;cancel.Enabled=Busy;account.Enabled=!Busy;language.Enabled=!Busy;}
    void Purchase(string action){
        if(!account.Checked){MessageBox.Show(T("selectAccount"),Text);return;}
        if(MessageBox.Show(T(action=="pro12"?"confirmFirst":"confirmStack"),Text,MessageBoxButtons.YesNo,MessageBoxIcon.Question)==DialogResult.Yes)Run(action);
    }
    void Run(string action){
        if(Busy)return;
        string exe=Path.Combine(root,"runtime","worker","AndroidWorker.exe"),adb=Path.Combine(root,"runtime","adb.exe");
        if(!File.Exists(exe)||!File.Exists(adb)){MessageBox.Show(T("unpack"),Text);return;}
        if(action=="check"||action=="open-login")ready=false;
        if(action=="open-login")account.Checked=false;
        statusKey=null;status.Text=T("running")+action;
        Append("\r\n── "+DateTime.Now.ToString("HH:mm:ss")+" · "+action+" ──");
        var p=new Process();
        p.StartInfo=new ProcessStartInfo(exe,action+" --adb \""+adb+"\""){UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true,RedirectStandardInput=true,StandardOutputEncoding=Encoding.UTF8,StandardErrorEncoding=Encoding.UTF8,WorkingDirectory=data};
        p.StartInfo.EnvironmentVariables["ANDROID_HELPER_DATA"]=data;
        p.StartInfo.EnvironmentVariables["ANDROID_HELPER_LANGUAGE"]=prefs.English?"en":"ru";
        p.StartInfo.EnvironmentVariables["PYTHONIOENCODING"]="utf-8";
        p.EnableRaisingEvents=true;
        p.OutputDataReceived+=delegate(object sender,DataReceivedEventArgs e){if(e.Data!=null)Dispatch(()=>ReadLine(e.Data));};
        p.ErrorDataReceived+=delegate(object sender,DataReceivedEventArgs e){if(e.Data!=null)Dispatch(()=>Append(e.Data));};
        p.Exited+=delegate{p.WaitForExit();Dispatch(()=>{
            if(p.ExitCode!=0){SetStatus("failure");if(action=="check")ready=false;}
            else SetStatus(action=="check"?"ready":action=="list"?"listed":action=="open-login"?"loginOpened":action=="subscriptions"||action=="play"?"opened":"review");
            UpdateButtons();
        });};
        try{worker=p;p.Start();p.BeginOutputReadLine();p.BeginErrorReadLine();p.StandardInput.Close();UpdateButtons();}
        catch(Exception e){worker=null;statusKey=null;status.Text=T("startError")+e.Message;UpdateButtons();}
    }
    void ReadLine(string line){
        if(!line.StartsWith("@@")){Append(line);return;}
        try{var entry=json.Deserialize<Dictionary<string,object>>(line.Substring(2));string kind=(string)entry["kind"];
            if(kind=="ready")ready=true;
            if(entry.ContainsKey("text")){statusKey=null;status.Text=(string)entry["text"];Append(status.Text);}
            if(kind=="result")Append(T("result")+(string)entry["status"]);
        }catch{Append(line);}
    }
    void Append(string text){log.AppendText(text+Environment.NewLine);try{File.AppendAllText(Path.Combine(data,"application.log"),text+Environment.NewLine,Encoding.UTF8);}catch{}}
    void Dispatch(Action action){if(!IsDisposed&&IsHandleCreated)try{BeginInvoke(action);}catch(InvalidOperationException){}}
    void Stop(){try{if(Busy){var info=new ProcessStartInfo("taskkill.exe","/PID "+worker.Id+" /T /F"){UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true};using(var p=Process.Start(info))p.WaitForExit();}}catch(Exception e){Append(e.Message);}SetStatus("stopped");}
    void OpenFolder(string path){if(Directory.Exists(path))Process.Start("explorer.exe","\""+path+"\"");}
    void OpenFile(string path){if(File.Exists(path))Process.Start("notepad.exe","\""+path+"\"");}
    [STAThread] static void Main(string[] args){
        Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
        var app=new AndroidHelper();
        if(args.Length>=2&&args[0]=="--preview"){
            app.prefs.Dark=Array.IndexOf(args,"--dark")>=0;app.prefs.English=Array.IndexOf(args,"--en")>=0;
            app.ApplyLabels();app.ApplyTheme();app.Show();Application.DoEvents();
            using(var image=new Bitmap(app.Width,app.Height)){app.DrawToBitmap(image,new Rectangle(0,0,app.Width,app.Height));image.Save(args[1]);}
            app.Close();return;
        }
        Application.Run(app);
    }
}
