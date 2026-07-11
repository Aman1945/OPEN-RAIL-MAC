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

namespace ORTS.Common
{
    /// <summary>
    /// Cross-platform filesystem compatibility helpers.
    ///
    /// MSTS/Open Rails content and much of the engine code build file paths using the
    /// Windows directory separator '\'. On non-Windows platforms '\' is a legal filename
    /// character rather than a separator, so those paths fail to resolve. Windows .NET file
    /// APIs accept '/' as a separator too, so normalizing '\' to '/' is safe on every platform.
    /// (macOS' default filesystem is case-insensitive, so no case-folding is required there.)
    /// </summary>
    public static class FileSystemCompat
    {
        public static string NormalizePath(string path)
        {
            if (string.IsNullOrEmpty(path))
                return path;
#if WINDOWS
            return path;
#else
            return path.Replace('\\', '/');
#endif
        }
    }
}
