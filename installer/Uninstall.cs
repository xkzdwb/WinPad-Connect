using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Win32;

internal static class Uninstall
{
    [STAThread]
    private static void Main(string[] args)
    {
        string dir = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
        bool silent = args.Length > 0 && string.Equals(args[0], "/S", StringComparison.OrdinalIgnoreCase);

        if (args.Length > 1 && string.Equals(args[0], "/RUN", StringComparison.OrdinalIgnoreCase))
        {
            Run(args[1].Trim('"'));
            return;
        }

        if (!silent)
        {
            DialogResult answer = MessageBox.Show(
                "确定卸载 Win-Pad Connect？\n\n将删除程序文件、开始菜单与桌面快捷方式。\n" +
                "数据目录 %APPDATA%\\Win-Pad Connect（设置、备份、报告）会保留。",
                "卸载 Win-Pad Connect", MessageBoxButtons.YesNo, MessageBoxIcon.Question);
            if (answer != DialogResult.Yes) return;
        }

        // 复制自身到临时目录后再删除安装目录，避免“文件正在使用”
        string temp = Path.Combine(Path.GetTempPath(), "wpc-uninstall-" + Guid.NewGuid().ToString("N") + ".exe");
        File.Copy(Application.ExecutablePath, temp, true);
        Process.Start(new ProcessStartInfo(temp, "/RUN \"" + dir + "\"") { UseShellExecute = false });
    }

    private static void Run(string dir)
    {
        Thread.Sleep(700);
        try
        {
            string programs = Environment.GetFolderPath(Environment.SpecialFolder.Programs);
            string menuDir = Path.Combine(programs, "Win-Pad Connect");
            if (Directory.Exists(menuDir)) Directory.Delete(menuDir, true);

            string desktop = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "Win-Pad Connect.lnk");
            if (File.Exists(desktop)) File.Delete(desktop);

            try
            {
                Registry.CurrentUser.DeleteSubKeyTree(
                    @"Software\Microsoft\Windows\CurrentVersion\Uninstall\WinPadConnect", false);
            }
            catch { }
            try { Registry.CurrentUser.DeleteSubKeyTree(@"Software\WinPadConnect", false); } catch { }

            try { Directory.Delete(dir, true); }
            catch
            {
                // 仍有文件占用时交给系统命令延迟删除
                Process.Start(new ProcessStartInfo("cmd.exe",
                    "/c ping -n 3 127.0.0.1 >nul & rmdir /s /q \"" + dir + "\"")
                { CreateNoWindow = true, UseShellExecute = false });
            }
        }
        catch (Exception ex)
        {
            if (Environment.UserInteractive)
                MessageBox.Show("卸载时出错：" + ex.Message, "Win-Pad Connect");
        }
    }
}
