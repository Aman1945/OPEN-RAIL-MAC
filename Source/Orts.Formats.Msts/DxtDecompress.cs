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

namespace Orts.Formats.Msts
{
    /// <summary>
    /// CPU decompressor for DXT1/DXT3/DXT5 (S3TC) compressed texture blocks into 32-bit RGBA.
    ///
    /// MonoGame's DesktopGL backend does not reliably render S3TC-compressed textures on macOS, which shows
    /// up as garbled/glitchy surfaces. On those platforms Open Rails decompresses MSTS .ace DXT textures here
    /// and uploads them as plain SurfaceFormat.Color (RGBA) instead.
    /// </summary>
    public static class DxtDecompress
    {
        // 0x12 = DXT1, 0x14 = DXT3, 0x16 = DXT5 (the ACE surface-format codes).
        public static bool IsDxt(int aceSurfaceFormat) => aceSurfaceFormat == 0x12 || aceSurfaceFormat == 0x14 || aceSurfaceFormat == 0x16;

        /// <summary>Decompress a DXT block buffer to RGBA bytes (R,G,B,A order). Returns width*height*4 bytes.</summary>
        public static byte[] Decode(byte[] src, int width, int height, int aceSurfaceFormat)
        {
            var dst = new byte[width * height * 4];
            var blocksX = Math.Max(1, (width + 3) / 4);
            var blocksY = Math.Max(1, (height + 3) / 4);
            var pos = 0;
            var dxt1 = aceSurfaceFormat == 0x12;
            var dxt3 = aceSurfaceFormat == 0x14;

            // Scratch buffers reused for every block (a 2048 x 2048 texture has 262,144 blocks).
            var alpha = new byte[16];
            var av = new int[8];
            var r = new int[4]; var g = new int[4]; var b = new int[4];

            for (var by = 0; by < blocksY; by++)
            {
                for (var bx = 0; bx < blocksX; bx++)
                {
                    for (var i = 0; i < 16; i++) alpha[i] = 255;

                    if (dxt3)
                    {
                        if (pos + 8 > src.Length) return dst;
                        for (var i = 0; i < 8; i++)
                        {
                            var ab = src[pos + i];
                            alpha[i * 2] = (byte)((ab & 0x0F) * 17);
                            alpha[i * 2 + 1] = (byte)((ab >> 4) * 17);
                        }
                        pos += 8;
                    }
                    else if (!dxt1)
                    {
                        // DXT5 interpolated alpha.
                        if (pos + 8 > src.Length) return dst;
                        var a0 = src[pos];
                        var a1 = src[pos + 1];
                        av[0] = a0; av[1] = a1;
                        if (a0 > a1)
                            for (var i = 1; i < 7; i++) av[i + 1] = ((7 - i) * a0 + i * a1) / 7;
                        else
                        {
                            for (var i = 1; i < 5; i++) av[i + 1] = ((5 - i) * a0 + i * a1) / 5;
                            av[6] = 0; av[7] = 255;
                        }
                        long bits = 0;
                        for (var i = 0; i < 6; i++) bits |= ((long)src[pos + 2 + i]) << (8 * i);
                        for (var i = 0; i < 16; i++) alpha[i] = (byte)av[(int)((bits >> (3 * i)) & 0x7)];
                        pos += 8;
                    }

                    // Colour block (DXT1-style) — 2x RGB565 endpoints + 16x 2-bit indices.
                    if (pos + 8 > src.Length) return dst;
                    int c0 = src[pos] | (src[pos + 1] << 8);
                    int c1 = src[pos + 2] | (src[pos + 3] << 8);
                    Rgb565(c0, out r[0], out g[0], out b[0]);
                    Rgb565(c1, out r[1], out g[1], out b[1]);
                    if (dxt1 && c0 <= c1)
                    {
                        r[2] = (r[0] + r[1]) / 2; g[2] = (g[0] + g[1]) / 2; b[2] = (b[0] + b[1]) / 2;
                        r[3] = g[3] = b[3] = 0; // transparent black in 1-bit-alpha DXT1
                    }
                    else
                    {
                        r[2] = (2 * r[0] + r[1]) / 3; g[2] = (2 * g[0] + g[1]) / 3; b[2] = (2 * b[0] + b[1]) / 3;
                        r[3] = (r[0] + 2 * r[1]) / 3; g[3] = (g[0] + 2 * g[1]) / 3; b[3] = (b[0] + 2 * b[1]) / 3;
                    }
                    var idx = src[pos + 4] | (src[pos + 5] << 8) | (src[pos + 6] << 16) | (src[pos + 7] << 24);
                    pos += 8;

                    for (var py = 0; py < 4; py++)
                    {
                        for (var px = 0; px < 4; px++)
                        {
                            var pixel = py * 4 + px;
                            var code = (idx >> (2 * pixel)) & 0x3;
                            var x = bx * 4 + px;
                            var y = by * 4 + py;
                            if (x >= width || y >= height) continue;
                            var o = (y * width + x) * 4;
                            var a = alpha[pixel];
                            if (dxt1 && c0 <= c1 && code == 3) a = 0; // punch-through alpha
                            dst[o] = (byte)r[code];
                            dst[o + 1] = (byte)g[code];
                            dst[o + 2] = (byte)b[code];
                            dst[o + 3] = a;
                        }
                    }
                }
            }
            return dst;
        }

        static void Rgb565(int c, out int r, out int g, out int b)
        {
            r = ((c >> 11) & 0x1F) * 255 / 31;
            g = ((c >> 5) & 0x3F) * 255 / 63;
            b = (c & 0x1F) * 255 / 31;
        }
    }
}
