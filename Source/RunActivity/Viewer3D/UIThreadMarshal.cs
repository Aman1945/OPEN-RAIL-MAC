// COPYRIGHT 2024 by the Open Rails project.
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

#if !WINDOWS
using System;
using System.Reflection;

namespace Orts.Viewer3D
{
    /// <summary>
    /// Runs an action on MonoGame's render (UI) thread.
    ///
    /// Open Rails was written for WindowsDX, which allows GPU resource work on any thread. MonoGame's
    /// DesktopGL backend requires all GL calls on the render thread and throws "Operation not called on
    /// UI thread" for things like Texture2D.GetData() invoked from the Loader thread. MonoGame already
    /// marshals resource *creation* to the render thread via its internal Threading.BlockOnUIThread; this
    /// helper exposes that same mechanism (via reflection) so the rest of Open Rails' loader code can
    /// marshal GPU readback/copy operations too. The render loop services these once per frame.
    /// </summary>
    public static class UIThreadMarshal
    {
        static readonly Action<Action> BlockOnUIThreadDelegate;
        static readonly Action RunDelegate;

        static UIThreadMarshal()
        {
            try
            {
                var monoGameAssembly = typeof(Microsoft.Xna.Framework.Game).Assembly;
                var threadingType = monoGameAssembly.GetType("Microsoft.Xna.Framework.Threading");
                var method = threadingType?.GetMethod("BlockOnUIThread",
                    BindingFlags.NonPublic | BindingFlags.Static, null, new[] { typeof(Action) }, null);
                if (method != null)
                    BlockOnUIThreadDelegate = (Action<Action>)Delegate.CreateDelegate(typeof(Action<Action>), method);

                // Threading.Run() drains actions queued by BlockOnUIThread; must be called on the render thread.
                var runMethod = threadingType?.GetMethod("Run",
                    BindingFlags.NonPublic | BindingFlags.Static, null, System.Type.EmptyTypes, null);
                if (runMethod != null)
                    RunDelegate = (Action)Delegate.CreateDelegate(typeof(Action), runMethod);
            }
            catch
            {
                BlockOnUIThreadDelegate = null;
                RunDelegate = null;
            }
        }

        /// <summary>
        /// Drains GPU actions queued by background threads via BlockOnUIThread. MUST be called from the
        /// render (UI) thread. Used so the render thread can service background-thread GPU work while it
        /// would otherwise be blocked waiting for the Updater/Loader (avoids a cross-thread GL deadlock).
        /// </summary>
        public static void PumpUIThread()
        {
            RunDelegate?.Invoke();
        }

        /// <summary>
        /// Runs <paramref name="action"/> on the render thread and blocks until it completes. If the
        /// MonoGame marshalling hook is unavailable, runs it inline (correct on Windows / when already on the UI thread).
        /// </summary>
        public static void Run(Action action)
        {
            if (BlockOnUIThreadDelegate != null)
                BlockOnUIThreadDelegate(action);
            else
                action();
        }
    }
}
#endif
