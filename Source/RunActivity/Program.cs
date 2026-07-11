// COPYRIGHT 2013 by the Open Rails project.
// 
// This file is part of Open Rails.
// 
// Open Rails is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
// 
// Open Rails is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
// 
// You should have received a copy of the GNU General Public License
// along with Open Rails.  If not, see <http://www.gnu.org/licenses/>.

using System;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
#if WINDOWS
using System.Windows.Forms;
#endif
using Orts.Common;
using Orts.Simulation;
using Orts.Viewer3D;
#if WINDOWS
using Orts.Viewer3D.Debugging;
#endif
using Orts.Viewer3D.Processes;
using ORTS.Common;
using ORTS.Settings;

namespace Orts
{
#if WINDOWS
    static class NativeMethods
    {
        [DllImport("kernel32.dll", CallingConvention = CallingConvention.StdCall)]
        internal static extern bool SetDllDirectory(string pathName);
    }
#endif

    static class Program
    {
        public static Simulator Simulator;
        public static Viewer Viewer;
#if WINDOWS
        public static MapViewer MapForm;
        public static SoundDebugForm SoundDebugForm;
#endif
        public static ORTraceListener ORTraceListener;
        public static string logFileName = "";          // contains path to file
        public static string EvaluationFilename = "";   // contains path to file

        /// <summary>
        /// The main entry point for the application.
        /// </summary>
        [ThreadName("Render")]
        static void Main(string[] args)
        {
#if !WINDOWS
            // Map hardcoded Windows DllImport names (e.g. "OpenAL32.dll") to the platform's native libraries.
            NativeLibrary.SetDllImportResolver(typeof(Program).Assembly, ResolveNativeLibrary);
#endif

#if WINDOWS
            var options = args.Where(a => a.StartsWith("-") || a.StartsWith("/")).Select(a => a.Substring(1));
#else
            // On non-Windows platforms '/' begins an absolute file path, so only '-' introduces an option.
            var options = args.Where(a => a.StartsWith("-")).Select(a => a.Substring(1));
#endif
            var settings = new UserSettings(options);

#if WINDOWS
            //enables loading of dll for specific architecture(32 or 64bit) from distinct folders, useful when both versions require same name (as for OpenAL32.dll)
            string path = Path.Combine(ApplicationInfo.ProcessDirectory, "Native");
            path = Path.Combine(path, (Environment.Is64BitProcess) ? "X64" : "X86");
            NativeMethods.SetDllDirectory(path);

            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
#endif

            var game = new Game(settings);
            game.PushState(new GameStateRunActivity(args));
            game.Run();
        }

#if !WINDOWS
        static IntPtr ResolveNativeLibrary(string libraryName, System.Reflection.Assembly assembly, DllImportSearchPath? searchPath)
        {
            if (libraryName == "OpenAL32.dll")
            {
                var candidates = new[] {
                    "libopenal.dylib", "libopenal.1.dylib", "libopenal.so.1", "openal",
                    "/opt/homebrew/lib/libopenal.dylib", "/opt/homebrew/opt/openal-soft/lib/libopenal.dylib",
                    "/usr/local/lib/libopenal.dylib", "/usr/local/opt/openal-soft/lib/libopenal.dylib",
                    "/System/Library/Frameworks/OpenAL.framework/OpenAL",
                };
                foreach (var candidate in candidates)
                    if (NativeLibrary.TryLoad(candidate, out var handle))
                        return handle;
            }
            return IntPtr.Zero;
        }
#endif
    }
}
