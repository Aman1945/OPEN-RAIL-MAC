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
using System.IO;

namespace ORTS.Common
{
    /// <summary>
    /// Minimal cross-platform read-only INI file parser, for content (e.g. script parameter) files
    /// that are read via a simple section/key lookup. Not related to user-settings storage.
    /// </summary>
    public static class SimpleIniReader
    {
        /// <summary>
        /// Returns the value of "keyName" under "[sectionName]" in the given INI file, or null if not found.
        /// </summary>
        public static string GetValue(string sectionName, string keyName, string filePath)
        {
            if (!File.Exists(filePath))
                return null;

            string currentSection = null;
            foreach (var rawLine in File.ReadAllLines(filePath))
            {
                var line = rawLine.Trim();
                if (line.Length == 0 || line.StartsWith(";"))
                    continue;
                if (line.StartsWith("[") && line.EndsWith("]"))
                {
                    currentSection = line.Substring(1, line.Length - 2);
                    continue;
                }
                if (!string.Equals(currentSection, sectionName, StringComparison.OrdinalIgnoreCase))
                    continue;
                var eq = line.IndexOf('=');
                if (eq < 0)
                    continue;
                var key = line.Substring(0, eq).Trim();
                if (string.Equals(key, keyName, StringComparison.OrdinalIgnoreCase))
                    return line.Substring(eq + 1).Trim();
            }
            return null;
        }
    }
}
