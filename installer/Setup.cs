using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Win32;

internal static class Program
{
    internal const string AppName = "Win-Pad Connect";
    internal const string AppVersion = "1.0.0";
    internal const string Author = "lzx_xkzdwb";
    internal const string GitHubUrl = "https://github.com/xkzdwb";
    internal const string RepoUrl = "https://github.com/xkzdwb/WinPad-Connect";

    [STAThread]
    private static int Main(string[] args)
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);

        bool silent = false;
        string dir = null;
        foreach (string arg in args)
        {
            if (string.Equals(arg, "/S", StringComparison.OrdinalIgnoreCase)) silent = true;
            else if (arg.StartsWith("/DIR=", StringComparison.OrdinalIgnoreCase))
                dir = arg.Substring(5).Trim('"');
        }

        if (silent)
        {
            string target = dir
                ?? Environment.GetEnvironmentVariable("WPC_INSTALL_DIR")
                ?? Installer.DefaultDir;
            bool test = Environment.GetEnvironmentVariable("WPC_TEST_INSTALL") == "1";
            int code = Installer.Install(target, !test, false, true, delegate { }, test);
            return code;
        }

        Application.Run(new SetupForm(dir));
        return 0;
    }
}

internal sealed class SetupForm : Form
{
    private readonly TextBox _path;
    private readonly CheckBox _desktop;
    private readonly CheckBox _launch;
    private readonly Label _status;
    private readonly Button _install;
    private readonly Button _browse;

    internal SetupForm(string preset)
    {
        Text = Program.AppName + " 安装程序";
        ClientSize = new Size(620, 520);
        StartPosition = FormStartPosition.CenterScreen;
        FormBorderStyle = FormBorderStyle.FixedSingle;
        MaximizeBox = false;
        BackColor = Color.FromArgb(11, 18, 32);
        ForeColor = Color.FromArgb(230, 237, 247);
        Font = new Font("Microsoft YaHei UI", 9F);

        var header = new Panel { Dock = DockStyle.Top, Height = 136, BackColor = Color.FromArgb(14, 22, 40) };
        var bar = new Panel { Dock = DockStyle.Left, Width = 6, BackColor = Color.FromArgb(61, 220, 151) };
        header.Controls.Add(bar);
        header.Controls.Add(new Label
        {
            Text = Program.AppName,
            Font = new Font("Microsoft YaHei UI", 22F, FontStyle.Bold),
            ForeColor = Color.FromArgb(230, 237, 247),
            AutoSize = true,
            Location = new Point(30, 22),
        });
        header.Controls.Add(new Label
        {
            Text = "Windows 主机端 · 体检 / 编码参数锁定 / 平板接入服务",
            Font = new Font("Microsoft YaHei UI", 9F),
            ForeColor = Color.FromArgb(141, 162, 192),
            AutoSize = true,
            Location = new Point(32, 66),
        });
        header.Controls.Add(new Label
        {
            Text = "作者 " + Program.Author + " · " + Program.GitHubUrl,
            Font = new Font("Microsoft YaHei UI", 8F),
            ForeColor = Color.FromArgb(93, 114, 144),
            AutoSize = true,
            Location = new Point(32, 88),
        });
        header.Controls.Add(new Label
        {
            Text = "项目仓库 " + Program.RepoUrl,
            Font = new Font("Microsoft YaHei UI", 8F),
            ForeColor = Color.FromArgb(93, 114, 144),
            AutoSize = true,
            Location = new Point(32, 106),
        });
        header.Controls.Add(new Label
        {
            Text = "v" + Program.AppVersion,
            ForeColor = Color.FromArgb(90, 169, 255),
            AutoSize = true,
            Location = new Point(540, 30),
        });

        var body = new Panel { Dock = DockStyle.Fill, Padding = new Padding(30, 22, 30, 16) };
        Controls.Add(body);
        Controls.Add(header);

        body.Controls.Add(new Label
        {
            Text = "安装位置",
            ForeColor = Color.FromArgb(141, 162, 192),
            AutoSize = true,
            Location = new Point(0, 4),
        });

        _path = new TextBox
        {
            Text = preset ?? Installer.DefaultDir,
            Location = new Point(0, 28),
            Width = 440,
            BackColor = Color.FromArgb(19, 30, 51),
            ForeColor = Color.FromArgb(230, 237, 247),
            BorderStyle = BorderStyle.FixedSingle,
        };
        body.Controls.Add(_path);

        _browse = new Button
        {
            Text = "浏览…",
            Location = new Point(450, 27),
            Width = 96,
            Height = 25,
            FlatStyle = FlatStyle.Flat,
            BackColor = Color.FromArgb(23, 36, 60),
            ForeColor = Color.FromArgb(230, 237, 247),
        };
        _browse.FlatAppearance.BorderColor = Color.FromArgb(34, 50, 79);
        _browse.Click += delegate
        {
            using (var dialog = new FolderBrowserDialog())
            {
                dialog.Description = "选择安装位置";
                if (dialog.ShowDialog(this) == DialogResult.OK)
                    _path.Text = Path.Combine(dialog.SelectedPath, Program.AppName);
            }
        };
        body.Controls.Add(_browse);

        _desktop = new CheckBox
        {
            Text = "创建桌面快捷方式",
            Checked = true,
            Location = new Point(0, 76),
            Width = 260,
            ForeColor = Color.FromArgb(230, 237, 247),
        };
        body.Controls.Add(_desktop);

        _launch = new CheckBox
        {
            Text = "安装完成后启动",
            Checked = true,
            Location = new Point(0, 104),
            Width = 260,
            ForeColor = Color.FromArgb(230, 237, 247),
        };
        body.Controls.Add(_launch);

        body.Controls.Add(new Label
        {
            Text = "需要 Python 3.10+（安装时勾选 Add python.exe to PATH）。\n" +
                   "数据保存在 %APPDATA%\\" + Program.AppName + "，端口 47800 / 47801。",
            Location = new Point(0, 142),
            Width = 540,
            Height = 48,
            ForeColor = Color.FromArgb(93, 114, 144),
        });

        _status = new Label
        {
            Text = "准备就绪。",
            Location = new Point(0, 206),
            Width = 540,
            Height = 44,
            ForeColor = Color.FromArgb(141, 162, 192),
        };
        body.Controls.Add(_status);

        _install = new Button
        {
            Text = "安装",
            Location = new Point(354, 300),
            Width = 190,
            Height = 40,
            FlatStyle = FlatStyle.Flat,
            BackColor = Color.FromArgb(61, 220, 151),
            ForeColor = Color.FromArgb(11, 18, 32),
            Font = new Font("Microsoft YaHei UI", 10F, FontStyle.Bold),
        };
        _install.FlatAppearance.BorderSize = 0;
        _install.Click += InstallClicked;
        body.Controls.Add(_install);

        body.Controls.Add(new Label
        {
            Text = "卸载可在“设置 → 应用”或开始菜单中找到。安装包未签名，SmartScreen 提示时选择“更多信息 → 仍要运行”。",
            Location = new Point(0, 352),
            Width = 560,
            Height = 40,
            ForeColor = Color.FromArgb(93, 114, 144),
            Font = new Font("Microsoft YaHei UI", 8F),
        });
    }

    private void InstallClicked(object sender, EventArgs e)
    {
        string target = _path.Text.Trim();
        if (target.Length == 0)
        {
            MessageBox.Show(this, "请选择安装位置。", Program.AppName);
            return;
        }
        _install.Enabled = false;
        _browse.Enabled = false;
        _path.Enabled = false;

        bool launch = _launch.Checked;
        bool desktop = _desktop.Checked;

        var thread = new Thread(delegate ()
        {
            int code = Installer.Install(target, desktop, launch, false, delegate (string message)
            {
                try
                {
                    BeginInvoke((Action)delegate
                    {
                        _status.Text = message;
                        _status.Refresh();
                    });
                }
                catch { }
            });

            try
            {
                BeginInvoke((Action)delegate
                {
                    if (code == 0)
                    {
                        _status.Text = "安装完成。开始菜单与桌面快捷方式已创建。";
                        _install.Text = "完成";
                        _install.Enabled = true;
                        _install.Click -= InstallClicked;
                        _install.Click += delegate { Close(); };
                    }
                    else
                    {
                        _status.Text = "安装失败，请检查目录权限或关闭正在运行的程序后重试。";
                        _install.Enabled = true;
                    }
                });
            }
            catch { }
        });
        thread.IsBackground = true;
        thread.Start();
    }
}

internal static class Installer
{
    internal static string DefaultDir
    {
        get
        {
            return Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "Programs", Program.AppName);
        }
    }


    internal static string LogPath()
    {
        string env = Environment.GetEnvironmentVariable("WPC_LOG");
        return string.IsNullOrEmpty(env)
            ? Path.Combine(Path.GetTempPath(), "wpc-setup.log")
            : env;
    }

    internal static void Log(string message)
    {
        try { File.AppendAllText(LogPath(), message + Environment.NewLine); } catch { }
    }

    internal static int Install(string target, bool desktop, bool launch, bool silent, Action<string> status,
        bool testOnly = false)
    {
        try
        {
            Log("enter target=" + target);
            target = Path.GetFullPath(target);
            if (Directory.Exists(target))
            {
                if (!silent)
                {
                    var answer = MessageBox.Show(
                        "目录已存在，覆盖安装会先删除旧文件：\n" + target + "\n\n继续？",
                        Program.AppName, MessageBoxButtons.YesNo, MessageBoxIcon.Question);
                    if (answer != DialogResult.Yes)
                    {
                        status("已取消。");
                        return 2;
                    }
                }
                Directory.Delete(target, true);
            }
            Directory.CreateDirectory(target);

            status("正在解压文件…");
            string temp = Path.Combine(Path.GetDirectoryName(target), ".wpc-setup-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(temp);
            string zipPath = Path.Combine(temp, "payload.zip");
            using (Stream input = Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip"))
            {
                if (input == null) throw new InvalidOperationException("安装载荷缺失");
                using (var output = File.Create(zipPath)) input.CopyTo(output);
            }
            string extract = Path.Combine(temp, "files");
            Log("extracting");
            ZipFile.ExtractToDirectory(zipPath, extract);
            Log("extracted");
            CopyDirectory(extract, target);
            Log("copied");

            string launcher = Path.Combine(target, Program.AppName + ".exe");
            string uninstaller = Path.Combine(target, "Uninstall.exe");
            if (!File.Exists(launcher)) throw new FileNotFoundException("启动器缺失", launcher);

            if (testOnly)
            {
                status("测试模式：跳过快捷方式与注册表。");
                return 0;
            }

            status("正在创建快捷方式…");
            string programs = Environment.GetFolderPath(Environment.SpecialFolder.Programs);
            string menuDir = Path.Combine(programs, Program.AppName);
            Directory.CreateDirectory(menuDir);
            CreateShortcut(Path.Combine(menuDir, Program.AppName + ".lnk"), launcher, target,
                "Windows 主机端 · Moonlight / Sunshine 装配台", launcher);
            CreateShortcut(Path.Combine(menuDir, "卸载 " + Program.AppName + ".lnk"), uninstaller, target,
                "卸载 " + Program.AppName, uninstaller);
            string quick = Path.Combine(target, "快速开始.txt");
            if (File.Exists(quick))
                CreateShortcut(Path.Combine(menuDir, "快速开始.lnk"), quick, target, "快速开始", launcher);

            if (desktop)
            {
                string desktopDir = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
                CreateShortcut(Path.Combine(desktopDir, Program.AppName + ".lnk"), launcher, target,
                    "Windows 主机端 · Moonlight / Sunshine 装配台", launcher);
            }

            status("正在写入卸载信息…");
            long sizeKb = 0;
            foreach (string file in Directory.GetFiles(target, "*", SearchOption.AllDirectories))
                sizeKb += new FileInfo(file).Length / 1024;

            using (RegistryKey key = Registry.CurrentUser.CreateSubKey(
                @"Software\Microsoft\Windows\CurrentVersion\Uninstall\WinPadConnect"))
            {
                key.SetValue("DisplayName", Program.AppName);
                key.SetValue("DisplayVersion", Program.AppVersion);
                key.SetValue("Publisher", Program.Author);
                key.SetValue("InstallLocation", target);
                key.SetValue("DisplayIcon", launcher);
                key.SetValue("UninstallString", "\"" + uninstaller + "\"");
                key.SetValue("NoModify", 1, RegistryValueKind.DWord);
                key.SetValue("NoRepair", 1, RegistryValueKind.DWord);
                key.SetValue("EstimatedSize", (int)sizeKb, RegistryValueKind.DWord);
            }
            using (RegistryKey key = Registry.CurrentUser.CreateSubKey(@"Software\WinPadConnect"))
            {
                key.SetValue("InstallDir", target);
                key.SetValue("Version", Program.AppVersion);
            }

            File.WriteAllText(Path.Combine(target, "install.json"),
                "{\"name\":\"" + Program.AppName + "\",\"version\":\"" + Program.AppVersion +
                "\",\"installed_at\":\"" + DateTime.Now.ToString("s") + "\"}");

            try { Directory.Delete(temp, true); } catch { }
            status("安装完成。");
            if (launch)
            {
                try { Process.Start(new ProcessStartInfo(launcher) { WorkingDirectory = target }); }
                catch { }
            }
            return 0;
        }
        catch (Exception ex)
        {
            Log("ERR " + ex);
            status("安装失败：" + ex.Message);
            if (silent)
            {
                try
                {
                    File.WriteAllText(Path.Combine(Path.GetTempPath(), "wpc-install-error.txt"), ex.ToString()); try { File.WriteAllText(Path.Combine(Path.GetDirectoryName(Application.ExecutablePath), "setup-error.txt"), ex.ToString()); } catch { }
                }
                catch { }
            }
            else
            {
                MessageBox.Show(ex.ToString(), Program.AppName + " 安装失败",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            return 1;
        }
    }

    private static void CopyDirectory(string source, string target)
    {
        foreach (string dir in Directory.GetDirectories(source, "*", SearchOption.AllDirectories))
            Directory.CreateDirectory(dir.Replace(source, target));
        foreach (string file in Directory.GetFiles(source, "*", SearchOption.AllDirectories))
        {
            string destination = file.Replace(source, target);
            Directory.CreateDirectory(Path.GetDirectoryName(destination));
            File.Copy(file, destination, true);
        }
    }

    private static void CreateShortcut(string link, string targetPath, string workDir, string description, string icon)
    {
        Type shellType = Type.GetTypeFromProgID("WScript.Shell");
        if (shellType == null) throw new InvalidOperationException("WScript.Shell 不可用");
        object shell = Activator.CreateInstance(shellType);
        object shortcut = shellType.InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell,
            new object[] { link });
        Type type = shortcut.GetType();
        type.InvokeMember("TargetPath", BindingFlags.SetProperty, null, shortcut, new object[] { targetPath });
        type.InvokeMember("WorkingDirectory", BindingFlags.SetProperty, null, shortcut, new object[] { workDir });
        type.InvokeMember("Description", BindingFlags.SetProperty, null, shortcut, new object[] { description });
        type.InvokeMember("IconLocation", BindingFlags.SetProperty, null, shortcut, new object[] { icon + ",0" });
        type.InvokeMember("Save", BindingFlags.InvokeMethod, null, shortcut, null);
    }
}
