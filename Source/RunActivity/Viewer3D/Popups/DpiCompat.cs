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

using System;

namespace Orts.Viewer3D.Popups
{
    /// <summary>
    /// Provides the system vertical DPI. On Windows this queries GDI+; on other platforms
    /// (where System.Drawing.Common is unavailable) it returns 96 (i.e. a 1.0 scale factor).
    /// </summary>
    public static class DpiCompat
    {
        public static float DpiY
        {
            get
            {
#if WINDOWS
                return System.Drawing.Graphics.FromHwnd(IntPtr.Zero).DpiY;
#else
                return 96f;
#endif
            }
        }
    }
}
