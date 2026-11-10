using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Windows.Forms;

internal static class Launcher
{
    [STAThread]
    private static void Main(string[] args)
    {
        string dir = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
        string pythonw = FindPythonw();
        if (pythonw == null)
        {
            MessageBox.Show(
                "未找到 Python 3.10 或更高版本。\n\n" +
                "Win-Pad Connect 需要 Python 运行环境：\n" +
                "1. 打开 https://www.python.org/downloads/windows/ 下载安装包；\n" +
                "2. 安装时勾选 “Add python.exe to PATH”；\n" +
                "3. 重新启动本程序。\n\n" +
                "已安装但未生效时，可设置环境变量 WINPAD_PYTHONW 指向 pythonw.exe。",
                "Win-Pad Connect",
                MessageBoxButtons.OK,
                MessageBoxIcon.Warning);
            return;
        }

        bool console = false;
        var forwarded = new List<string>();
        foreach (string arg in args)
        {
            if (string.Equals(arg, "--console", StringComparison.OrdinalIgnoreCase))
            {
                console = true;
            }
            else
            {
                forwarded.Add(arg);
            }
        }

        var command = new StringBuilder();
        if (IsPyLauncher(pythonw))
        {
            command.Append("-3 ");
        }
        command.Append("-m padlink");
        foreach (string arg in forwarded)
        {
            command.Append(' ').Append(Quote(arg));
        }

        string python = console
            ? pythonw.Replace("pythonw.exe", "python.exe").Replace("pyw.exe", "py.exe")
            : pythonw;

        string appDir = Path.Combine(dir, "app");
        if (!Directory.Exists(appDir)) appDir = dir;

        var psi = new ProcessStartInfo(python, command.ToString())
        {
            WorkingDirectory = appDir,
            UseShellExecute = false,
            CreateNoWindow = !console,
        };
        try
        {
            Process.Start(psi);
        }
        catch (Exception ex)
        {
            MessageBox.Show("启动失败：" + ex.Message, "Win-Pad Connect",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private static bool IsPyLauncher(string exe)
    {
        string name = Path.GetFileName(exe).ToLowerInvariant();
        return name == "pyw.exe" || name == "py.exe";
    }

    private static string Quote(string value)
    {
        if (value.Length > 0 && value.IndexOfAny(new[] { ' ', '\t', '"' }) < 0)
        {
            return value;
        }
        return "\"" + value.Replace("\"", "\\\"") + "\"";
    }

    private static string FindPythonw()
    {
        string overridePath = Environment.GetEnvironmentVariable("WINPAD_PYTHONW");
        if (!string.IsNullOrEmpty(overridePath) && File.Exists(overridePath))
        {
            return overridePath;
        }

        string path = Environment.GetEnvironmentVariable("PATH") ?? string.Empty;
        foreach (string part in path.Split(';'))
        {
            if (string.IsNullOrWhiteSpace(part)) continue;
            foreach (string name in new[] { "pythonw.exe", "pyw.exe" })
            {
                try
                {
                    string candidate = Path.Combine(part.Trim().Trim('"'), name);
                    if (File.Exists(candidate)) return candidate;
                }
                catch { }
            }
        }

        string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        string found = NewestUnder(Path.Combine(local, "Programs", "Python"), "pythonw.exe");
        if (found != null) return found;

        foreach (string root in new[] { @"C:\Python", @"C:\Program Files\Python" })
        {
            found = NewestUnder(root, "pythonw.exe");
            if (found != null) return found;
        }

        foreach (string root in new[] { @"C:\Program Files (x86)\Python", @"C:\Python27" })
        {
            found = NewestUnder(root, "pyw.exe");
            if (found != null) return found;
        }
        return null;
    }

    private static string NewestUnder(string root, string fileName)
    {
        try
        {
            if (!Directory.Exists(root)) return null;
            var dirs = new List<string>(Directory.GetDirectories(root));
            dirs.Sort(StringComparer.OrdinalIgnoreCase);
            dirs.Reverse();
            foreach (string dir in dirs)
            {
                string candidate = Path.Combine(dir, fileName);
                if (File.Exists(candidate)) return candidate;
            }
            string direct = Path.Combine(root, fileName);
            if (File.Exists(direct)) return direct;
        }
        catch { }
        return null;
    }
}
