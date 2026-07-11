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
using SkiaSharp;
using GdiFontStyle = System.Drawing.FontStyle;
using GdiGraphicsUnit = System.Drawing.GraphicsUnit;

namespace Orts.Viewer3D.Popups
{
    /// <summary>
    /// A cross-platform stand-in for System.Drawing.Font, backed by SkiaSharp.
    /// .NET 8+ blocks System.Drawing.Common on non-Windows platforms, so the WindowText
    /// glyph-atlas subsystem uses this instead when building for macOS/Linux.
    /// </summary>
    public sealed class SkiaFont : IDisposable
    {
        public readonly SKFont Font;
        public readonly SKPaint Paint;

        public SkiaFont(string family, float pixelSize, GdiFontStyle style, GdiGraphicsUnit unit)
        {
            var weight = (style & GdiFontStyle.Bold) != 0 ? SKFontStyleWeight.Bold : SKFontStyleWeight.Normal;
            var slant = (style & GdiFontStyle.Italic) != 0 ? SKFontStyleSlant.Italic : SKFontStyleSlant.Upright;
            var typeface = SKTypeface.FromFamilyName(family, weight, SKFontStyleWidth.Normal, slant) ?? SKTypeface.Default;
            Font = new SKFont(typeface, pixelSize) { Subpixel = true, Edging = SKFontEdging.Antialias };
            Paint = new SKPaint(Font) { Color = SKColors.White, IsAntialias = true };
        }

        /// <summary>Line height in pixels (matches System.Drawing.Font.GetHeight semantics closely enough).</summary>
        public float GetHeight()
        {
            var m = Font.Metrics;
            return m.Descent - m.Ascent + m.Leading;
        }

        /// <summary>Rounded line height, as System.Drawing.Font.Height.</summary>
        public int Height => (int)Math.Ceiling(GetHeight());

        /// <summary>Advance width of a string in pixels.</summary>
        public float MeasureWidth(string text) => Paint.MeasureText(text);

        /// <summary>Distance from the top of the glyph box to the text baseline, for DrawText positioning.</summary>
        public float Ascent => -Font.Metrics.Ascent;

        public void Dispose()
        {
            Paint?.Dispose();
            Font?.Dispose();
        }
    }
}
#endif
