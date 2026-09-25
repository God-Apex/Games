using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;

namespace ApexKasino
{
    static class Pal
    {
        public static readonly Color Night = Color.FromArgb(2, 10, 24);
        public static readonly Color Panel = Color.FromArgb(6, 26, 56);
        public static readonly Color Panel2 = Color.FromArgb(11, 36, 71);
        public static readonly Color Panel3 = Color.FromArgb(17, 48, 92);
        public static readonly Color Line = Color.FromArgb(18, 56, 107);
        public static readonly Color Text = Color.FromArgb(234, 243, 255);
        public static readonly Color Muted = Color.FromArgb(143, 176, 214);
        public static readonly Color Dim = Color.FromArgb(88, 116, 156);
        public static readonly Color Navy = Color.FromArgb(0, 68, 148);
        public static readonly Color Cyan = Color.FromArgb(0, 152, 198);
        public static readonly Color Yellow = Color.FromArgb(255, 221, 0);
        public static readonly Color Cream = Color.FromArgb(255, 235, 127);
        public static readonly Color Green = Color.FromArgb(46, 190, 90);
        public static readonly Color Red = Color.FromArgb(240, 60, 70);
        public static readonly Color Gold = Color.FromArgb(201, 162, 39);
        public static readonly Color Ink = Color.FromArgb(6, 22, 46);
    }

    // kreslení objektů (statické části) a pomocné funkce
    partial class GameForm
    {
        readonly Dictionary<int, SolidBrush> brushes = new Dictionary<int, SolidBrush>();
        readonly Dictionary<long, Pen> pens = new Dictionary<long, Pen>();
        readonly Dictionary<int, Font> fonts = new Dictionary<int, Font>();
        static readonly StringFormat CenterFmt = new StringFormat { Alignment = StringAlignment.Center, LineAlignment = StringAlignment.Center, FormatFlags = StringFormatFlags.NoWrap };
        static readonly StringFormat RightFmt = new StringFormat { Alignment = StringAlignment.Far, LineAlignment = StringAlignment.Near, FormatFlags = StringFormatFlags.NoWrap };
        static readonly StringFormat ClipFmt = new StringFormat { Trimming = StringTrimming.EllipsisCharacter, FormatFlags = StringFormatFlags.NoWrap };

        SolidBrush B(Color c)
        {
            SolidBrush b;
            if (!brushes.TryGetValue(c.ToArgb(), out b)) { b = new SolidBrush(c); brushes[c.ToArgb()] = b; }
            return b;
        }

        SolidBrush B(int a, Color c) { return B(Color.FromArgb(Math.Max(0, Math.Min(255, a)), c)); }

        Pen P(Color c, float w)
        {
            long key = ((long)c.ToArgb() << 16) ^ (long)(w * 100);
            Pen p;
            if (!pens.TryGetValue(key, out p)) { p = new Pen(c, w); pens[key] = p; }
            return p;
        }

        Font F(float px, bool bold)
        {
            int key = (int)(px * 10) * 2 + (bold ? 1 : 0);
            Font f;
            if (!fonts.TryGetValue(key, out f)) { f = new Font("Segoe UI", px, bold ? FontStyle.Bold : FontStyle.Regular, GraphicsUnit.Pixel); fonts[key] = f; }
            return f;
        }

        void Txt(Graphics g, string s, Font f, Color c, float x, float y) { g.DrawString(s, f, B(c), x, y); }
        void TxtC(Graphics g, string s, Font f, Color c, float cx, float cy) { g.DrawString(s, f, B(c), new RectangleF(cx - 400, cy - 60, 800, 120), CenterFmt); }
        void TxtR(Graphics g, string s, Font f, Color c, float rx, float y) { g.DrawString(s, f, B(c), new RectangleF(rx - 600, y, 600, 200), RightFmt); }
        void TxtClip(Graphics g, string s, Font f, Color c, RectangleF r) { g.DrawString(s, f, B(c), r, ClipFmt); }
        void TxtWrap(Graphics g, string s, Font f, Color c, RectangleF r) { g.DrawString(s, f, B(c), r); }
        float TextW(Graphics g, string s, Font f) { return g.MeasureString(s, f, 2000, StringFormat.GenericTypographic).Width; }

        static GraphicsPath RoundPath(RectangleF r, float rad)
        {
            var p = new GraphicsPath();
            float d = Math.Min(rad * 2, Math.Min(r.Width, r.Height));
            if (d <= .5f) { p.AddRectangle(r); return p; }
            p.AddArc(r.X, r.Y, d, d, 180, 90);
            p.AddArc(r.Right - d, r.Y, d, d, 270, 90);
            p.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
            p.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
            p.CloseFigure();
            return p;
        }

        static void FillRound(Graphics g, Brush b, RectangleF r, float rad) { using (var p = RoundPath(r, rad)) g.FillPath(b, p); }
        static void DrawRound(Graphics g, Pen pen, RectangleF r, float rad) { using (var p = RoundPath(r, rad)) g.DrawPath(pen, p); }

        static Color Mix(Color a, Color b, float t)
        {
            t = Math.Max(0, Math.Min(1, t));
            return Color.FromArgb((int)(a.A + (b.A - a.A) * t), (int)(a.R + (b.R - a.R) * t), (int)(a.G + (b.G - a.G) * t), (int)(a.B + (b.B - a.B) * t));
        }

        void Shadow(Graphics g, RectangleF r, float rad) { FillRound(g, B(95, Color.Black), new RectangleF(r.X + 2, r.Y + 3, r.Width, r.Height), rad); }

        void Grad(Graphics g, RectangleF r, Color a, Color b, float angle, float rad)
        {
            if (r.Width < 1 || r.Height < 1) return;
            using (var br = new LinearGradientBrush(new RectangleF(r.X - .5f, r.Y - .5f, r.Width + 1, r.Height + 1), a, b, angle)) FillRound(g, br, r, rad);
        }

        static readonly Color[] PyrCols = { Pal.Cream, Color.FromArgb(128, 194, 160), Pal.Cyan, Color.FromArgb(0, 110, 172), Pal.Navy };

        void DrawPyramid(Graphics g, float cx, float top, float w, float h)
        {
            int n = PyrCols.Length;
            float band = h / n, gap = Math.Max(.6f, h / 22);
            for (int i = 0; i < n; i++)
            {
                float y0 = top + i * band, y1 = top + (i + 1) * band - (i < n - 1 ? gap : 0);
                float h0 = w / 2 * (y0 - top) / h, h1 = w / 2 * (y1 - top) / h;
                g.FillPolygon(B(PyrCols[i]), new[] { new PointF(cx - h0, y0), new PointF(cx + h0, y0), new PointF(cx + h1, y1), new PointF(cx - h1, y1) });
            }
        }

        void DrawStar(Graphics g, float cx, float cy, float r, Color c)
        {
            var pts = new PointF[10];
            for (int i = 0; i < 10; i++)
            {
                double a = -Math.PI / 2 + i * Math.PI / 5;
                float rr = i % 2 == 0 ? r : r * .45f;
                pts[i] = new PointF(cx + (float)Math.Cos(a) * rr, cy + (float)Math.Sin(a) * rr);
            }
            g.FillPolygon(B(c), pts);
        }

        void Check(Graphics g, float x, float y, float s, Color c)
        {
            var p = P(c, s * .22f);
            g.DrawLines(p, new[] { new PointF(x, y + s * .5f), new PointF(x + s * .38f, y + s * .85f), new PointF(x + s, y + s * .1f) });
        }

        // symboly válců: 0 sedmička, 1 třešně, 2 zvonek, 3 BAR, 4 čtyřlístek
        void DrawSym(Graphics g, int s, RectangleF c)
        {
            g.FillRectangle(B(Color.FromArgb(244, 247, 251)), c);
            float cx = c.X + c.Width / 2, cy = c.Y + c.Height / 2, r = Math.Min(c.Width, c.Height) * .3f;
            switch (s)
            {
                case 0:
                    TxtC(g, "7", F(c.Height * .95f, true), Color.FromArgb(224, 20, 43), cx, cy + .3f);
                    break;
                case 1:
                    g.FillEllipse(B(Color.FromArgb(224, 20, 43)), cx - r * 1.3f, cy - r * .2f, r * 1.2f, r * 1.2f);
                    g.FillEllipse(B(Color.FromArgb(224, 20, 43)), cx + r * .1f, cy, r * 1.2f, r * 1.2f);
                    g.DrawLine(P(Color.FromArgb(47, 158, 68), Math.Max(.6f, r * .3f)), cx - r * .6f, cy, cx + r * .3f, cy - r * 1.4f);
                    break;
                case 2:
                    g.FillPie(B(Color.FromArgb(255, 190, 0)), cx - r * 1.2f, cy - r * 1.3f, r * 2.4f, r * 2.8f, 180, 180);
                    g.FillRectangle(B(Color.FromArgb(179, 116, 0)), cx - r * 1.2f, cy + r * .05f, r * 2.4f, r * .45f);
                    break;
                case 3:
                    g.FillRectangle(B(Color.FromArgb(20, 20, 24)), c.X + c.Width * .12f, cy - r * .7f, c.Width * .76f, r * 1.4f);
                    g.FillRectangle(B(Color.White), c.X + c.Width * .22f, cy - r * .12f, c.Width * .56f, r * .24f);
                    break;
                default:
                    {
                        var gb = B(Color.FromArgb(34, 176, 75));
                        float q = r * .95f;
                        g.FillEllipse(gb, cx - q, cy - q, q, q); g.FillEllipse(gb, cx, cy - q, q, q);
                        g.FillEllipse(gb, cx - q, cy, q, q); g.FillEllipse(gb, cx, cy, q, q);
                        break;
                    }
            }
        }

        // ---------- statická grafika objektů (souřadnice půdorysu, 32 px na pole) ----------

        void DrawArt(Graphics g, ObjType t, int dir)
        {
            bool down = dir != 2;
            switch (t.Id)
            {
                case "classic": SlotArt(g, 0, 0, down, Pal.Cyan, false); break;
                case "retro": SlotArt2(g, 0, 0, down, Color.FromArgb(210, 40, 50), 4, Color.FromArgb(190, 196, 206), Color.FromArgb(96, 104, 118), Color.FromArgb(230, 234, 240)); break;
                case "clover": SlotArt2(g, 0, 0, down, Color.FromArgb(40, 170, 80), 2, Color.FromArgb(30, 84, 56), Color.FromArgb(10, 34, 24), Color.FromArgb(90, 200, 120)); break;
                case "diamond": SlotArt2(g, 0, 0, down, Color.FromArgb(150, 80, 220), 3, Color.FromArgb(70, 40, 110), Color.FromArgb(26, 14, 48), Color.FromArgb(190, 150, 250)); break;
                case "tower": SlotArt2(g, 0, 0, down, Pal.Gold, 5, Color.FromArgb(34, 34, 40), Color.FromArgb(8, 8, 10), Pal.Gold); break;
                case "multi": MultiArt(g, down); break;
                case "wheel": WheelArt(g, down); break;
                case "pyramid": SlotArt(g, 0, 0, down, Pal.Yellow, true); break;
                case "station": StationArt(g, down); break;
                case "island": IslandArt(g); break;
                case "blackjack": BlackjackArt(g); break;
                case "roulette": RouletteArt(g); break;
                case "poker": PokerArt(g); break;
                case "bar": BarArt(g, down); break;
                case "wc": WcArt(g); break;
                case "atm": AtmArt(g, down); break;
                case "sofa": SofaArt(g, down); break;
                case "bin": BinArt(g); break;
                case "plant": PlantArt(g); break;
                case "palm": PalmArt(g); break;
                case "led": LedArt(g); break;
                case "fountain": FountainArt(g); break;
                case "statue": StatueArt(g); break;
            }
        }

        // obdélník v půdorysu, zrcadlený svisle podle orientace
        static RectangleF RY(bool down, float fh, float x0, float y0, float x, float y, float w, float h)
        {
            return down ? new RectangleF(x0 + x, y0 + y, w, h) : new RectangleF(x0 + x, y0 + fh - y - h, w, h);
        }

        static RectangleF SlotScreen(float x0, float y0, bool down) { return RY(down, 32, x0, y0, 6, 11, 20, 11); }

        // topper: 0 tečky, 1 pyramida, 2 čtyřlístek, 3 diamant, 4 sedmička, 5 VIP
        void SlotArt2(Graphics g, float x0, float y0, bool down, Color accent, int topper, Color bodyTop, Color bodyBot, Color edge)
        {
            var body = RY(down, 32, x0, y0, 3, 1, 26, 28);
            Shadow(g, body, 5);
            Grad(g, body, bodyTop, bodyBot, down ? 90f : 270f, 5);
            DrawRound(g, P(edge, topper == 5 ? 1.4f : 1), body, 5);
            var top = RY(down, 32, x0, y0, 5, 2, 22, 7);
            FillRound(g, B(accent), top, 3);
            g.FillRectangle(B(80, Color.White), top.X + 2, top.Y + 1, top.Width - 4, 1.2f);
            float cx = top.X + top.Width / 2, cy = top.Y + top.Height / 2;
            switch (topper)
            {
                case 2:
                    {
                        var gb = B(Color.FromArgb(200, 255, 200));
                        g.FillEllipse(gb, cx - 3.2f, cy - 3, 3, 3); g.FillEllipse(gb, cx + .2f, cy - 3, 3, 3);
                        g.FillEllipse(gb, cx - 3.2f, cy, 3, 3); g.FillEllipse(gb, cx + .2f, cy, 3, 3);
                        break;
                    }
                case 3:
                    g.FillPolygon(B(Color.FromArgb(160, 240, 255)), new[] { new PointF(cx, cy - 3), new PointF(cx + 4, cy), new PointF(cx, cy + 3), new PointF(cx - 4, cy) });
                    g.DrawLine(P(Color.White, .6f), cx - 4, cy, cx + 4, cy);
                    break;
                case 4: TxtC(g, "777", F(5.6f, true), Color.White, cx, cy + .2f); break;
                case 5: TxtC(g, "VIP", F(5.6f, true), Pal.Ink, cx, cy + .2f); break;
                default: for (int i = 0; i < 3; i++) g.FillEllipse(B(Pal.Ink), top.X + 5 + i * 5, top.Y + 2.2f, 2.6f, 2.6f); break;
            }
            var scr = SlotScreen(x0, y0, down);
            g.FillRectangle(B(Color.FromArgb(4, 8, 18)), scr.X - 1, scr.Y - 1, scr.Width + 2, scr.Height + 2);
            if (topper == 5) g.DrawRectangle(P(Pal.Gold, .8f), scr.X - 1.5f, scr.Y - 1.5f, scr.Width + 3, scr.Height + 3);
            var deck = RY(down, 32, x0, y0, 4, 23, 24, 6);
            FillRound(g, B(Color.FromArgb(12, 18, 32)), deck, 2);
            Color[] bc = { Pal.Red, Pal.Yellow, Pal.Green };
            for (int i = 0; i < 3; i++) g.FillEllipse(B(bc[i]), deck.X + 4 + i * 6, deck.Y + 1.6f, 4, 2.8f);
            g.FillRectangle(B(accent), deck.Right - 6, deck.Y + 2, 3, 2);
        }

        void MultiArt(Graphics g, bool down)
        {
            var body = RY(down, 32, 0, 0, 2, 1, 92, 28);
            Shadow(g, body, 6);
            Grad(g, body, Color.FromArgb(40, 60, 100), Color.FromArgb(12, 20, 40), down ? 90f : 270f, 6);
            DrawRound(g, P(Color.FromArgb(90, 130, 190), 1), body, 6);
            var top = RY(down, 32, 0, 0, 5, 2, 86, 7);
            using (var br = new LinearGradientBrush(new RectangleF(top.X - 1, top.Y, top.Width + 2, top.Height), Pal.Cyan, Pal.Navy, 0f)) FillRound(g, br, top, 3);
            TxtC(g, "MULTI-GAME", F(5.4f, true), Pal.Cream, 48, top.Y + top.Height / 2 + .2f);
            foreach (var s in MultiScreens(down)) g.FillRectangle(B(Color.FromArgb(4, 8, 18)), s.X - 1, s.Y - 1, s.Width + 2, s.Height + 2);
            var deck = RY(down, 32, 0, 0, 4, 23, 88, 6);
            FillRound(g, B(Color.FromArgb(12, 18, 32)), deck, 2);
            for (int k = 0; k < 3; k++)
            {
                for (int i = 0; i < 3; i++) g.FillEllipse(B(i == 0 ? Pal.Red : i == 1 ? Pal.Yellow : Pal.Green), deck.X + 5 + k * 30.5f + i * 6, deck.Y + 1.6f, 4, 2.8f);
                if (k > 0) g.DrawLine(P(Color.FromArgb(70, 100, 150), .8f), 2 + k * 30.7f, body.Y + 2, 2 + k * 30.7f, body.Bottom - 2);
            }
        }

        static RectangleF[] MultiScreens(bool down)
        {
            return new[] { RY(down, 32, 0, 0, 6, 11, 24, 11), RY(down, 32, 0, 0, 36.5f, 11, 24, 11), RY(down, 32, 0, 0, 67, 11, 24, 11) };
        }

        void WheelArt(Graphics g, bool down)
        {
            var body = RY(down, 32, 0, 0, 2, 1, 60, 28);
            Shadow(g, body, 6);
            Grad(g, body, Color.FromArgb(110, 30, 40), Color.FromArgb(40, 10, 16), down ? 90f : 270f, 6);
            DrawRound(g, P(Pal.Gold, 1.2f), body, 6);
            foreach (var s in WheelScreens(down)) g.FillRectangle(B(Color.FromArgb(4, 8, 18)), s.X - 1, s.Y - 1, s.Width + 2, s.Height + 2);
            var c = WheelCenter(down);
            g.FillEllipse(B(Pal.Gold), c.X - 11, c.Y - 11, 22, 22);
            var deck = RY(down, 32, 0, 0, 4, 23, 56, 6);
            FillRound(g, B(Color.FromArgb(30, 10, 14)), deck, 2);
            for (int k = 0; k < 2; k++)
                for (int i = 0; i < 3; i++)
                    g.FillEllipse(B(i == 0 ? Pal.Red : i == 1 ? Pal.Yellow : Pal.Green), deck.X + 5 + k * 34 + i * 6, deck.Y + 1.6f, 4, 2.8f);
        }

        static RectangleF[] WheelScreens(bool down)
        {
            return new[] { RY(down, 32, 0, 0, 4, 11, 16, 11), RY(down, 32, 0, 0, 44, 11, 16, 11) };
        }

        static PointF WheelCenter(bool down) { var r = RY(down, 32, 0, 0, 32, 12, 0, 0); return new PointF(32, r.Y); }

        void SlotArt(Graphics g, float x0, float y0, bool down, Color accent, bool pyr)
        {
            var body = RY(down, 32, x0, y0, 3, 1, 26, 28);
            Shadow(g, body, 5);
            Grad(g, body, Color.FromArgb(56, 72, 104), Color.FromArgb(16, 24, 42), down ? 90f : 270f, 5);
            DrawRound(g, P(Color.FromArgb(96, 128, 180), 1), body, 5);
            var top = RY(down, 32, x0, y0, 5, 2, 22, 7);
            FillRound(g, B(accent), top, 3);
            g.FillRectangle(B(80, Color.White), top.X + 2, top.Y + 1, top.Width - 4, 1.2f);
            if (pyr) DrawPyramid(g, top.X + top.Width / 2, top.Y + .6f, 11, 5.8f);
            else for (int i = 0; i < 3; i++) g.FillEllipse(B(Pal.Ink), top.X + 5 + i * 5, top.Y + 2.2f, 2.6f, 2.6f);
            var scr = SlotScreen(x0, y0, down);
            g.FillRectangle(B(Color.FromArgb(4, 8, 18)), scr.X - 1, scr.Y - 1, scr.Width + 2, scr.Height + 2);
            var deck = RY(down, 32, x0, y0, 4, 23, 24, 6);
            FillRound(g, B(Color.FromArgb(12, 18, 32)), deck, 2);
            Color[] bc = { Pal.Red, Pal.Yellow, Pal.Green };
            for (int i = 0; i < 3; i++) g.FillEllipse(B(bc[i]), deck.X + 4 + i * 6, deck.Y + 1.6f, 4, 2.8f);
            g.FillRectangle(B(Pal.Cyan), deck.Right - 6, deck.Y + 2, 3, 2);
        }

        void StationArt(Graphics g, bool down)
        {
            var body = RY(down, 32, 0, 0, 2, 1, 60, 28);
            Shadow(g, body, 6);
            Grad(g, body, Color.FromArgb(40, 60, 100), Color.FromArgb(12, 20, 40), down ? 90f : 270f, 6);
            DrawRound(g, P(Color.FromArgb(90, 130, 190), 1), body, 6);
            var top = RY(down, 32, 0, 0, 5, 2, 54, 7);
            using (var br = new LinearGradientBrush(new RectangleF(top.X - 1, top.Y, top.Width + 2, top.Height), Pal.Navy, Pal.Cyan, 0f)) FillRound(g, br, top, 3);
            DrawPyramid(g, 32, top.Y + .6f, 11, 5.8f);
            g.FillRectangle(B(Color.FromArgb(4, 8, 18)), RY(down, 32, 0, 0, 4, 10, 26, 13));
            g.FillRectangle(B(Color.FromArgb(4, 8, 18)), RY(down, 32, 0, 0, 34, 10, 26, 13));
            var deck = RY(down, 32, 0, 0, 4, 23, 56, 6);
            FillRound(g, B(Color.FromArgb(12, 18, 32)), deck, 2);
            for (int k = 0; k < 2; k++)
                for (int i = 0; i < 3; i++)
                    g.FillEllipse(B(i == 0 ? Pal.Red : i == 1 ? Pal.Yellow : Pal.Green), deck.X + 5 + k * 30 + i * 6, deck.Y + 1.6f, 4, 2.8f);
        }

        static RectangleF[] StationScreens(bool down)
        {
            return new[] { RY(down, 32, 0, 0, 5, 11, 24, 11), RY(down, 32, 0, 0, 35, 11, 24, 11) };
        }

        void IslandArt(Graphics g)
        {
            var bse = new RectangleF(1, 1, 62, 62);
            Shadow(g, bse, 10);
            Grad(g, bse, Pal.Cream, Pal.Gold, 45f, 10);
            FillRound(g, B(Color.FromArgb(10, 22, 46)), new RectangleF(3.5f, 3.5f, 57, 57), 8);
            SlotArt(g, 0, 0, false, Pal.Yellow, true);
            SlotArt(g, 32, 0, false, Pal.Yellow, true);
            SlotArt(g, 0, 32, true, Pal.Yellow, true);
            SlotArt(g, 32, 32, true, Pal.Yellow, true);
        }

        static RectangleF[] IslandScreens()
        {
            return new[] { SlotScreen(0, 0, false), SlotScreen(32, 0, false), SlotScreen(0, 32, true), SlotScreen(32, 32, true) };
        }

        void TableRim(Graphics g, GraphicsPath outer, GraphicsPath inner, Color felt1, Color felt2)
        {
            using (var sh = (GraphicsPath)outer.Clone())
            {
                var m = new Matrix(); m.Translate(2, 3); sh.Transform(m);
                g.FillPath(B(95, Color.Black), sh);
            }
            using (var br = new LinearGradientBrush(new RectangleF(0, 0, 96, 64), Color.FromArgb(128, 80, 40), Color.FromArgb(78, 46, 20), 90f)) g.FillPath(br, outer);
            using (var br = new LinearGradientBrush(new RectangleF(0, 0, 96, 64), felt1, felt2, 90f)) g.FillPath(br, inner);
            g.DrawPath(P(Color.FromArgb(60, 255, 235, 180), 1), inner);
        }

        void BlackjackArt(Graphics g)
        {
            using (var outer = new GraphicsPath())
            using (var inner = new GraphicsPath())
            {
                outer.AddArc(new RectangleF(3, -42, 90, 102), 0, 180); outer.CloseFigure();
                inner.AddArc(new RectangleF(8, -37, 80, 92), 0, 180); inner.CloseFigure();
                TableRim(g, outer, inner, Color.FromArgb(20, 130, 76), Color.FromArgb(10, 88, 48));
            }
            g.FillRectangle(B(Color.FromArgb(74, 42, 20)), 3, 7, 90, 5);
            FillRound(g, B(Color.FromArgb(12, 12, 16)), new RectangleF(34, 12, 28, 6), 1.5f);
            Color[] chips = { Pal.Red, Pal.Yellow, Pal.Cyan, Color.White, Pal.Green, Color.FromArgb(40, 40, 40) };
            for (int i = 0; i < 6; i++) g.FillRectangle(B(chips[i]), 35.5f + i * 4.4f, 13, 3.4f, 4);
            TxtC(g, "BLACKJACK", F(6.2f, true), Pal.Cream, 48, 27);
            TxtC(g, "pays 3 to 2", F(4.6f, false), Color.FromArgb(200, 255, 235, 180), 48, 33.5f);
            foreach (var c in BjSpots()) g.DrawEllipse(P(Color.FromArgb(160, 255, 235, 180), .8f), c.X - 5, c.Y - 5, 10, 10);
            // krupiér
            g.FillEllipse(B(95, Color.Black), 42, -1, 13, 9);
            g.FillEllipse(B(Color.White), 41.5f, -2.5f, 13, 9);
            g.FillEllipse(B(Color.FromArgb(20, 20, 24)), 44, -2, 8, 7);
            g.FillEllipse(B(Color.FromArgb(224, 172, 130)), 44.5f, -5, 7, 7);
        }

        static PointF[] BjSpots() { return new[] { new PointF(22, 40), new PointF(48, 47), new PointF(74, 40) }; }

        void RouletteArt(Graphics g)
        {
            using (var outer = RoundPath(new RectangleF(2, 4, 92, 56), 14))
            using (var inner = RoundPath(new RectangleF(6, 8, 84, 48), 11))
                TableRim(g, outer, inner, Color.FromArgb(20, 130, 76), Color.FromArgb(10, 88, 48));
            g.FillEllipse(B(95, Color.Black), 7, 14, 42, 42);
            using (var br = new LinearGradientBrush(new RectangleF(5, 11, 42, 42), Color.FromArgb(150, 96, 48), Color.FromArgb(70, 40, 18), 45f)) g.FillEllipse(br, 5, 11, 42, 42);
            // hrací pole
            g.FillRectangle(B(Color.FromArgb(20, 140, 70)), 54, 12, 32, 5);
            for (int c = 0; c < 4; c++)
                for (int r = 0; r < 3; r++)
                {
                    bool red = (c + r) % 2 == 0;
                    g.FillRectangle(B(red ? Color.FromArgb(200, 30, 40) : Color.FromArgb(20, 20, 24)), 54 + c * 8, 18 + r * 11, 8, 11);
                }
            var pen = P(Color.FromArgb(200, 255, 235, 180), .7f);
            g.DrawRectangle(pen, 54, 12, 32, 39);
            for (int c = 1; c < 4; c++) g.DrawLine(pen, 54 + c * 8, 18, 54 + c * 8, 51);
            for (int r = 0; r < 3; r++) g.DrawLine(pen, 54, 18 + r * 11, 86, 18 + r * 11);
            TxtC(g, "0", F(4.5f, true), Color.White, 70, 14.6f);
        }

        void PokerArt(Graphics g)
        {
            using (var outer = RoundPath(new RectangleF(2, 4, 92, 56), 28))
            using (var inner = RoundPath(new RectangleF(7, 9, 82, 46), 23))
                TableRim(g, outer, inner, Color.FromArgb(18, 80, 150), Color.FromArgb(8, 44, 100));
            g.DrawEllipse(P(Color.FromArgb(70, 255, 235, 180), 1), 22, 18, 52, 28);
            TxtC(g, "APEX POKER", F(5.5f, true), Color.FromArgb(150, 255, 235, 127), 48, 42);
            DrawPyramid(g, 48, 22, 12, 10);
        }

        void BarArt(Graphics g, bool down)
        {
            var shelf = RY(down, 32, 0, 0, 2, 1, 92, 9);
            Shadow(g, RY(down, 32, 0, 0, 1, 1, 94, 29), 3);
            FillRound(g, B(Color.FromArgb(58, 36, 20)), shelf, 2);
            Color[] bottles = { Color.FromArgb(46, 140, 70), Color.FromArgb(200, 130, 40), Color.FromArgb(200, 220, 230), Color.FromArgb(170, 30, 50), Color.FromArgb(90, 60, 30), Color.FromArgb(40, 90, 170) };
            for (int i = 0; i < 14; i++)
            {
                var r = RY(down, 32, 0, 0, 5 + i * 6.4f, 2.2f, 3.4f, 6.4f);
                g.FillRectangle(B(bottles[i % bottles.Length]), r);
                g.FillRectangle(B(110, Color.White), r.X + .6f, r.Y + 1, .9f, r.Height - 2);
            }
            g.FillRectangle(B(Color.FromArgb(28, 22, 18)), RY(down, 32, 0, 0, 2, 10, 92, 7));
            var counter = RY(down, 32, 0, 0, 1, 17, 94, 13);
            Grad(g, counter, Color.FromArgb(150, 98, 48), Color.FromArgb(92, 56, 24), down ? 90f : 270f, 3);
            g.FillRectangle(B(90, Color.White), RY(down, 32, 0, 0, 3, 18, 90, 1.2f));
            g.FillRectangle(B(Pal.Gold), RY(down, 32, 0, 0, 1, 28.5f, 94, 1.8f));
        }

        void WcArt(Graphics g)
        {
            var room = new RectangleF(2, 2, 60, 60);
            Shadow(g, room, 2);
            g.FillRectangle(B(Color.FromArgb(214, 224, 236)), room);
            var tile = P(Color.FromArgb(190, 204, 220), .8f);
            for (int i = 1; i < 8; i++) { g.DrawLine(tile, 2 + i * 7.5f, 2, 2 + i * 7.5f, 62); g.DrawLine(tile, 2, 2 + i * 7.5f, 62, 2 + i * 7.5f); }
            var wall = P(Color.FromArgb(52, 68, 92), 3.5f);
            g.DrawLine(wall, 2, 2, 62, 2); g.DrawLine(wall, 2, 2, 2, 62); g.DrawLine(wall, 62, 2, 62, 62);
            g.DrawLine(wall, 2, 62, 8, 62); g.DrawLine(wall, 24, 62, 40, 62); g.DrawLine(wall, 56, 62, 62, 62);
            g.DrawLine(wall, 32, 2, 32, 48);
            foreach (float x in new[] { 9f, 45f })
            {
                g.FillEllipse(B(Color.White), x, 7, 10, 13);
                g.DrawEllipse(P(Color.FromArgb(150, 160, 175), .8f), x, 7, 10, 13);
                g.FillRectangle(B(Color.FromArgb(230, 236, 244)), x - 1, 4, 12, 4);
            }
            g.FillRectangle(B(Color.White), 5, 40, 10, 6); g.FillRectangle(B(Color.White), 49, 40, 10, 6);
            FillRound(g, B(Pal.Navy), new RectangleF(24, 25, 16, 11), 2);
            TxtC(g, "WC", F(7, true), Color.White, 32, 30.5f);
        }

        void AtmArt(Graphics g, bool down)
        {
            var body = RY(down, 32, 0, 0, 6, 3, 20, 25);
            Shadow(g, body, 3);
            Grad(g, body, Color.FromArgb(170, 180, 196), Color.FromArgb(90, 100, 118), down ? 90f : 270f, 3);
            var head = RY(down, 32, 0, 0, 6, 3, 20, 6);
            FillRound(g, B(Pal.Navy), head, 2);
            TxtC(g, "ATM", F(4.8f, true), Color.White, head.X + head.Width / 2, head.Y + head.Height / 2);
            g.FillRectangle(B(Color.FromArgb(10, 20, 36)), RY(down, 32, 0, 0, 9, 11, 14, 8));
            var pad = RY(down, 32, 0, 0, 10, 21, 12, 5);
            g.FillRectangle(B(Color.FromArgb(60, 68, 84)), pad);
            for (int i = 0; i < 3; i++) for (int j = 0; j < 2; j++) g.FillRectangle(B(Color.FromArgb(200, 206, 216)), pad.X + 1 + i * 3.8f, pad.Y + .8f + j * 2.2f, 2.6f, 1.4f);
        }

        void SofaArt(Graphics g, bool down)
        {
            Shadow(g, RY(down, 32, 0, 0, 2, 2, 60, 26), 5);
            FillRound(g, B(Color.FromArgb(110, 20, 38)), RY(down, 32, 0, 0, 2, 2, 60, 11), 5);
            Grad(g, RY(down, 32, 0, 0, 7, 10, 50, 16), Color.FromArgb(190, 44, 70), Color.FromArgb(140, 28, 50), down ? 90f : 270f, 4);
            g.DrawLine(P(Color.FromArgb(110, 20, 38), 1), 32, RY(down, 32, 0, 0, 0, 11, 1, 14).Y, 32, RY(down, 32, 0, 0, 0, 11, 1, 14).Bottom);
            FillRound(g, B(Color.FromArgb(125, 24, 48)), RY(down, 32, 0, 0, 2, 8, 8, 20), 3);
            FillRound(g, B(Color.FromArgb(125, 24, 48)), RY(down, 32, 0, 0, 54, 8, 8, 20), 3);
            g.FillRectangle(B(50, Color.White), RY(down, 32, 0, 0, 9, 11.5f, 46, 1));
        }

        void BinArt(Graphics g)
        {
            g.FillEllipse(B(95, Color.Black), 10, 11, 14, 14);
            g.FillEllipse(B(Color.FromArgb(44, 52, 64)), 9, 9, 14, 14);
            g.DrawEllipse(P(Color.FromArgb(130, 145, 165), 1.6f), 9, 9, 14, 14);
            g.FillEllipse(B(Color.FromArgb(24, 30, 40)), 12, 12, 8, 8);
            g.DrawArc(P(Pal.Yellow, 1.4f), 10.5f, 10.5f, 11, 11, 200, 140);
        }

        void PlantArt(Graphics g)
        {
            g.FillEllipse(B(95, Color.Black), 9, 10, 16, 16);
            g.FillEllipse(B(Color.FromArgb(170, 86, 48)), 8, 8, 16, 16);
            g.DrawEllipse(P(Color.FromArgb(120, 58, 30), 1.2f), 8, 8, 16, 16);
            Color[] leaf = { Color.FromArgb(47, 158, 68), Color.FromArgb(55, 178, 77), Color.FromArgb(43, 138, 62) };
            var st = g.Save();
            g.TranslateTransform(16, 16);
            for (int i = 0; i < 7; i++)
            {
                g.RotateTransform(360f / 7);
                g.FillEllipse(B(leaf[i % 3]), -3, -12.5f, 6, 11);
            }
            g.Restore(st);
            g.FillEllipse(B(Color.FromArgb(30, 110, 50)), 13, 13, 6, 6);
        }

        void PalmArt(Graphics g)
        {
            g.FillEllipse(B(95, Color.Black), 10, 11, 14, 14);
            g.FillEllipse(B(Color.FromArgb(150, 120, 80)), 9, 9, 14, 14);
            var st = g.Save();
            g.TranslateTransform(16, 16);
            for (int i = 0; i < 7; i++)
            {
                g.RotateTransform(360f / 7);
                g.DrawLine(P(Color.FromArgb(40, 140, 60), 4.2f), 0, 0, 0, -15);
                g.DrawLine(P(Color.FromArgb(90, 190, 100), 1), 0, -2, 0, -14);
            }
            g.Restore(st);
            g.FillEllipse(B(Color.FromArgb(110, 80, 40)), 13.5f, 13.5f, 5, 5);
        }

        void LedArt(Graphics g)
        {
            g.FillRectangle(B(Color.FromArgb(110, 120, 134)), 9, 24, 3, 6); g.FillRectangle(B(Color.FromArgb(110, 120, 134)), 52, 24, 3, 6);
            var frame = new RectangleF(1, 6, 62, 19);
            Shadow(g, frame, 2);
            FillRound(g, B(Color.FromArgb(6, 8, 14)), frame, 2);
            DrawRound(g, P(Color.FromArgb(140, 152, 170), 1.3f), frame, 2);
            g.FillRectangle(B(Color.FromArgb(24, 6, 6)), 4, 9, 56, 13);
        }

        void FountainArt(Graphics g)
        {
            g.FillEllipse(B(95, Color.Black), 4, 5, 60, 60);
            using (var br = new LinearGradientBrush(new RectangleF(2, 2, 60, 60), Color.FromArgb(190, 198, 210), Color.FromArgb(110, 122, 140), 45f)) g.FillEllipse(br, 2, 2, 60, 60);
            using (var br = new LinearGradientBrush(new RectangleF(7, 7, 50, 50), Color.FromArgb(60, 180, 225), Color.FromArgb(10, 90, 160), 60f)) g.FillEllipse(br, 7, 7, 50, 50);
            g.FillEllipse(B(Color.FromArgb(170, 178, 192)), 25, 25, 14, 14);
            g.FillEllipse(B(Color.FromArgb(120, 200, 240)), 28, 28, 8, 8);
        }

        void StatueArt(Graphics g)
        {
            var ped = new RectangleF(4, 4, 56, 56);
            Shadow(g, ped, 6);
            Grad(g, ped, Color.FromArgb(240, 242, 246), Color.FromArgb(160, 168, 182), 45f, 6);
            DrawRound(g, P(Pal.Gold, 2), ped, 6);
            FillRound(g, B(Color.FromArgb(10, 28, 64)), new RectangleF(12, 12, 40, 40), 4);
            DrawPyramid(g, 32, 15, 34, 30);
            var rope = P(Color.FromArgb(170, 30, 50), 1.6f);
            g.DrawLine(rope, 8, 8, 56, 8); g.DrawLine(rope, 8, 56, 56, 56); g.DrawLine(rope, 8, 8, 8, 56); g.DrawLine(rope, 56, 8, 56, 56);
            foreach (var p in new[] { new PointF(8, 8), new PointF(56, 8), new PointF(8, 56), new PointF(56, 56) })
                g.FillEllipse(B(Pal.Gold), p.X - 3, p.Y - 3, 6, 6);
        }

        // ---------- textury a ikona ----------

        readonly TextureBrush[] carpets = new TextureBrush[3];
        // koberec podle patra: modrý, vínový, fialový VIP
        static readonly Color[][] CarpetCols = {
            new[] { Color.FromArgb(12, 32, 78), Color.FromArgb(20, 48, 104), Color.FromArgb(16, 40, 92) },
            new[] { Color.FromArgb(70, 14, 32), Color.FromArgb(98, 26, 46), Color.FromArgb(86, 20, 40) },
            new[] { Color.FromArgb(36, 16, 62), Color.FromArgb(56, 28, 90), Color.FromArgb(46, 22, 78) }
        };

        TextureBrush Carpet(int floor)
        {
            if (carpets[floor] != null) return carpets[floor];
            var cc = CarpetCols[floor];
            var bmp = new Bitmap(64, 64);
            using (var g = Graphics.FromImage(bmp))
            {
                g.SmoothingMode = SmoothingMode.AntiAlias;
                g.Clear(cc[0]);
                var p = new Pen(cc[1], 2.2f);
                g.DrawPolygon(p, new[] { new PointF(32, 2), new PointF(62, 32), new PointF(32, 62), new PointF(2, 32) });
                var p2 = new Pen(cc[2], 1.2f);
                g.DrawPolygon(p2, new[] { new PointF(32, 12), new PointF(52, 32), new PointF(32, 52), new PointF(12, 32) });
                using (var b = new SolidBrush(Color.FromArgb(70, 255, 221, 0)))
                {
                    var star = new PointF[8];
                    for (int i = 0; i < 8; i++)
                    {
                        double a = i * Math.PI / 4; float r = i % 2 == 0 ? 5 : 1.6f;
                        star[i] = new PointF(32 + (float)Math.Cos(a) * r, 32 + (float)Math.Sin(a) * r);
                    }
                    g.FillPolygon(b, star);
                }
                using (var b = new SolidBrush(Color.FromArgb(55, 0, 152, 198)))
                {
                    g.FillEllipse(b, -3, -3, 6, 6); g.FillEllipse(b, 61, -3, 6, 6);
                    g.FillEllipse(b, -3, 61, 6, 6); g.FillEllipse(b, 61, 61, 6, 6);
                }
                p.Dispose(); p2.Dispose();
            }
            carpets[floor] = new TextureBrush(bmp);
            return carpets[floor];
        }

        Icon MakeIcon()
        {
            var bmp = new Bitmap(32, 32);
            using (var g = Graphics.FromImage(bmp))
            {
                g.SmoothingMode = SmoothingMode.AntiAlias;
                g.Clear(Color.Transparent);
                DrawPyramid(g, 16, 3, 30, 26);
            }
            return Icon.FromHandle(bmp.GetHicon());
        }
    }
}
