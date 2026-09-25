using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Drawing.Text;
using System.Windows.Forms;

namespace ApexKasino
{
    // vykreslení herní plochy
    partial class GameForm
    {
        readonly Dictionary<string, Bitmap> sprites = new Dictionary<string, Bitmap>();
        float spriteScale = -1, floorScale = -1;
        Bitmap floorBmp;
        bool floorDirty = true;
        const int Pad = 8;

        // aktuální umístění světa: logický počátek a zvětšení
        float wx0 = MX, wy0 = MY, wz = 1;

        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics;
            g.Clear(Pal.Night);
            scale = Math.Min(ClientSize.Width / VW, ClientSize.Height / VH);
            ox = (ClientSize.Width - VW * scale) / 2; oy = (ClientSize.Height - VH * scale) / 2;
            g.TranslateTransform(ox, oy);
            g.ScaleTransform(scale, scale);
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.TextRenderingHint = TextRenderingHint.AntiAliasGridFit;
            g.SetClip(new RectangleF(0, 0, VW, VH));
            btns = new List<Btn>();
            hoverTip = null;
            CF = ViewF;

            if (OnTitle)
            {
                wz = Math.Min(VW / (GW * TS), VH / (GH * TS));
                wx0 = (VW - GW * TS * wz) / 2; wy0 = (VH - GH * TS * wz) / 2;
                DrawWorld(g);
                DrawTitle(g);
            }
            else
            {
                ComputeView();
                DrawWorld(g);
                DrawOverlaysOnMap(g);
                DrawTopBar(g);
                DrawRightPanel(g);
                DrawBottomPanel(g);
                if (screen == Screen.Menu) DrawMenu(g);
                if (screen == Screen.Help) DrawHelp(g);
                if (activeEvent != null && screen == Screen.Play) DrawEvent(g);
                if (bankrupt) DrawBankrupt(g);
            }
            btnsPrev = btns;
        }

        // kamera: přiblíží vlastněný sál tak, aby vyplnil herní okno
        void ComputeView()
        {
            var own = OwnLevels[ownLevel];
            float margin = ownLevel < 3 ? 1.4f : 0;
            wz = Math.Min(GW * TS / ((own.Width + margin) * TS), GH * TS / ((own.Height + margin) * TS));
            wz = Math.Max(1, Math.Min(1.8f, wz));
            float cx = own.X + own.Width / 2f, cy = own.Y + own.Height / 2f - (ownLevel < 3 ? .2f : 0);
            wx0 = MX + GW * TS / 2f - cx * TS * wz;
            wy0 = MY + GH * TS / 2f - cy * TS * wz;
            // nepouštět kameru za okraj mřížky
            wx0 = Math.Min(MX, Math.Max(MX + GW * TS - GW * TS * wz, wx0));
            wy0 = Math.Min(MY, Math.Max(MY + GH * TS - GH * TS * wz, wy0));
        }

        // otočení kanonické grafiky (čelem dolů) do směru dir
        static Matrix RotMatrix(ObjType t, int dir)
        {
            float w = t.W * TS, h = t.H * TS;
            switch (dir)
            {
                case 1: return new Matrix(0, 1, -1, 0, h, 0);
                case 2: return new Matrix(-1, 0, 0, -1, w, h);
                case 3: return new Matrix(0, -1, 1, 0, 0, w);
                default: return new Matrix();
            }
        }

        static void ApplyRot(Graphics g, ObjType t, int dir)
        {
            if (dir == 0 || (dir == 2 && t.Mirror)) return;
            using (var m = RotMatrix(t, dir)) g.MultiplyTransform(m);
        }

        static bool ArtDown(Obj o) { return !(o.Dir == 2 && o.T.Mirror); }

        float MouseWX { get { return (mouse.X - wx0) / (TS * wz); } }
        float MouseWY { get { return (mouse.Y - wy0) / (TS * wz); } }

        // ---------- svět ----------

        void DrawWorld(Graphics g)
        {
            float es = scale * wz;
            var st = g.Save();
            if (OnTitle) g.SetClip(new RectangleF(wx0, wy0, GW * TS * wz, GH * TS * wz), CombineMode.Intersect);
            else g.SetClip(new RectangleF(MX, MY, GW * TS, GH * TS), CombineMode.Intersect);

            // podlaha z cache (ostrá, v pixelech zařízení)
            if (floorBmp == null || floorDirty || floorScale != es)
            {
                if (floorBmp != null) floorBmp.Dispose();
                floorBmp = new Bitmap((int)Math.Ceiling(GW * TS * es), (int)Math.Ceiling(GH * TS * es), PixelFormat.Format32bppPArgb);
                using (var fg = Graphics.FromImage(floorBmp))
                {
                    fg.SmoothingMode = SmoothingMode.AntiAlias;
                    fg.TextRenderingHint = TextRenderingHint.AntiAliasGridFit;
                    fg.ScaleTransform(es, es);
                    RenderFloor(fg);
                }
                floorScale = es; floorDirty = false;
            }
            DrawDevice(g, floorBmp, wx0, wy0);

            g.TranslateTransform(wx0, wy0);
            g.ScaleTransform(wz, wz);

            bool building = screen == Screen.Play && (tool != null || sellTool);
            if (building)
            {
                var own = OwnLevels[ownLevel];
                var gp = P(Color.FromArgb(30, 255, 255, 255), 1);
                for (int x = own.Left; x <= own.Right; x++) g.DrawLine(gp, x * TS, own.Top * TS, x * TS, own.Bottom * TS);
                for (int y = own.Top; y <= own.Bottom; y++) g.DrawLine(gp, own.Left * TS, y * TS, own.Right * TS, y * TS);
                // místa pro hráče
                foreach (var o in objs)
                    foreach (var s in o.Seats)
                        if (Walkable(s.X, s.Y)) g.FillRectangle(B(22, Pal.Cyan), s.X * TS + 2, s.Y * TS + 2, TS - 4, TS - 4);
            }

            if (moodMap && !OnTitle) DrawMoodMap(g);

            // odpadky
            for (int i = 0; i < litter.Count; i++)
            {
                var p = litter[i];
                var c = i % 3 == 0 ? Color.FromArgb(235, 235, 225) : i % 3 == 1 ? Color.FromArgb(220, 60, 60) : Color.FromArgb(240, 200, 60);
                var st2 = g.Save();
                g.TranslateTransform(p.X * TS, p.Y * TS);
                g.RotateTransform(i * 47 % 180);
                g.FillRectangle(B(c), -2.2f, -1.4f, 4.4f, 2.8f);
                g.Restore(st2);
            }

            // objekty
            var sorted = new List<Obj>(objs);
            sorted.Sort((a, b) => a.Y != b.Y ? a.Y.CompareTo(b.Y) : a.X.CompareTo(b.X));
            foreach (var o in sorted)
            {
                var bmp = Sprite(o.T, o.Dir);
                DrawDevice(g, bmp, wx0 + (o.X * TS - Pad) * wz, wy0 + (o.Y * TS - Pad) * wz);
            }
            foreach (var o in sorted)
            {
                var s2 = g.Save();
                g.TranslateTransform(o.X * TS, o.Y * TS);
                var s3 = g.Save();
                ApplyRot(g, o.T, o.Dir);
                DrawDyn(g, o);
                g.Restore(s3);
                if (o.Broken) DrawBroken(g, o);
                g.Restore(s2);
            }

            // lidé
            var people = new List<Agent>();
            foreach (var gu in guests) if (!gu.Hidden && gu.Floor == viewFloor) people.Add(gu);
            foreach (var s in staff) if (s.Floor == viewFloor) people.Add(s);
            people.Sort((a, b) => a.Y.CompareTo(b.Y));
            foreach (var a in people)
            {
                var gu = a as Guest;
                if (gu != null) DrawGuest(g, gu); else DrawStaff(g, (Staff)a);
            }
            foreach (var gu in guests) if (!gu.Hidden && gu.Floor == viewFloor) DrawBubble(g, gu);

            // výběr
            if (screen == Screen.Play)
            {
                if (sel != null)
                {
                    var r = new RectangleF(sel.X * TS - 2, sel.Y * TS - 2, sel.W * TS + 4, sel.H * TS + 4);
                    DrawRound(g, P(Pal.Yellow, 2), r, 6);
                    foreach (var s in sel.Seats) g.DrawRectangle(P(120, Pal.Yellow), s.X * TS + 4, s.Y * TS + 4, TS - 8, TS - 8);
                }
                Agent sa = selGuest != null ? (Agent)selGuest : selStaff;
                if (sa != null) g.DrawEllipse(P(Pal.Yellow, 1.6f), SeatPos(sa).X - 11, SeatPos(sa).Y - 8, 22, 16);
                if (tool == null && !sellTool && InMap(mouse))
                {
                    int tx = (int)MouseWX, ty = (int)MouseWY;
                    var h = InGrid(tx, ty) ? occ[tx, ty] : null;
                    if (h != null && h != sel) DrawRound(g, P(90, Color.White), new RectangleF(h.X * TS - 1, h.Y * TS - 1, h.W * TS + 2, h.H * TS + 2), 6);
                }
                if (sellTool && InMap(mouse))
                {
                    int tx = (int)MouseWX, ty = (int)MouseWY;
                    var h = InGrid(tx, ty) ? occ[tx, ty] : null;
                    if (h != null)
                    {
                        var r = new RectangleF(h.X * TS, h.Y * TS, h.W * TS, h.H * TS);
                        g.FillRectangle(B(70, Pal.Red), r);
                        DrawRound(g, P(Pal.Red, 2), r, 4);
                    }
                }
            }

            // částice a texty
            foreach (var p in parts)
            {
                int a = (int)(255 * Math.Min(1, p.Life / .3f));
                if (p.Coin)
                {
                    g.FillEllipse(B(a, Pal.Gold), p.X * TS - 3, p.Y * TS - 3, 6, 6);
                    g.FillEllipse(B(a, Pal.Yellow), p.X * TS - 2.2f, p.Y * TS - 2.6f, 4.4f, 4.4f);
                }
                else g.FillRectangle(B(a, p.C), p.X * TS - p.Size / 2, p.Y * TS - p.Size / 2, p.Size, p.Size * .7f);
            }
            foreach (var t in texts)
            {
                int a = (int)(255 * Math.Min(1, t.Life / .5f));
                var f = F(11, true);
                TxtC(g, t.T, f, Color.FromArgb(a, Pal.Night), t.X * TS + 1, t.Y * TS - 6 + 1);
                TxtC(g, t.T, f, Color.FromArgb(a, t.C), t.X * TS, t.Y * TS - 6);
            }

            if (screen == Screen.Play && tool != null && InMap(mouse)) DrawGhost(g);
            g.Restore(st);
        }

        // jak se hostům líbí na každém poli (dekorace, odpadky)
        void DrawMoodMap(Graphics g)
        {
            var own = OwnLevels[ownLevel];
            for (int x = own.Left; x < own.Right; x++)
                for (int y = own.Top; y < own.Bottom; y++)
                {
                    if (!Walkable(x, y)) continue;
                    float v = MoodAt(x, y);
                    Color c = v > 0 ? Pal.Green : v > -.12f ? Pal.Yellow : Pal.Red;
                    int a = v > 0 ? (int)Math.Min(150, 60 + v * 900) : v > -.12f ? 45 : (int)Math.Min(150, 70 + -v * 200);
                    g.FillRectangle(B(a, c), x * TS + 1, y * TS + 1, TS - 2, TS - 2);
                }
        }

        void DrawDevice(Graphics g, Bitmap bmp, float lx, float ly)
        {
            var m = g.Transform;
            var im = g.InterpolationMode;
            g.ResetTransform();
            g.InterpolationMode = InterpolationMode.NearestNeighbor;
            g.PixelOffsetMode = PixelOffsetMode.Half;
            g.DrawImage(bmp, (int)Math.Round(ox + lx * scale), (int)Math.Round(oy + ly * scale), bmp.Width, bmp.Height);
            g.PixelOffsetMode = PixelOffsetMode.Default;
            g.InterpolationMode = im;
            g.Transform = m;
            m.Dispose();
        }

        Bitmap Sprite(ObjType t, int dir)
        {
            float es = scale * wz;
            if (spriteScale != es)
            {
                foreach (var b in sprites.Values) b.Dispose();
                sprites.Clear();
                spriteScale = es;
            }
            if (!t.Rot) dir = 0;
            string key = t.Id + dir;
            Bitmap bmp;
            if (!sprites.TryGetValue(key, out bmp))
            {
                var dm = Dims(t, dir);
                int w = (int)Math.Ceiling((dm.Width * TS + Pad * 2) * es), h = (int)Math.Ceiling((dm.Height * TS + Pad * 2) * es);
                bmp = new Bitmap(w, h, PixelFormat.Format32bppPArgb);
                using (var sg = Graphics.FromImage(bmp))
                {
                    sg.SmoothingMode = SmoothingMode.AntiAlias;
                    sg.TextRenderingHint = TextRenderingHint.AntiAliasGridFit;
                    sg.ScaleTransform(es, es);
                    sg.TranslateTransform(Pad, Pad);
                    ApplyRot(sg, t, dir);
                    DrawArt(sg, t, dir == 2 && t.Mirror ? 2 : 0);
                }
                sprites[key] = bmp;
            }
            return bmp;
        }

        void RenderFloor(Graphics g)
        {
            float W = GW * TS, H = GH * TS;
            g.FillRectangle(B(Color.FromArgb(5, 11, 22)), 0, 0, W, H);
            using (var hb = new HatchBrush(HatchStyle.WideUpwardDiagonal, Color.FromArgb(12, 24, 44), Color.FromArgb(5, 11, 22)))
                g.FillRectangle(hb, 0, 0, W, H);
            if (ownLevel < 3)
            {
                var nx = OwnLevels[ownLevel + 1];
                var r = new RectangleF(nx.X * TS, nx.Y * TS, nx.Width * TS, nx.Height * TS);
                using (var dp = new Pen(Color.FromArgb(90, Pal.Cyan), 1.5f) { DashStyle = DashStyle.Dash }) g.DrawRectangle(dp, r.X + 1, r.Y + 1, r.Width - 2, r.Height - 2);
                var cur = OwnLevels[ownLevel];
                float ty = (nx.Y + (cur.Y - nx.Y) / 2f) * TS;
                if (cur.Y - nx.Y >= 1)
                    TxtC(g, "Rozšíření sálu · " + FormatKc(OwnCost[ownLevel + 1]) + " · záložka Vylepšení", F(11, true), Color.FromArgb(150, Pal.Muted), r.X + r.Width / 2, ty);
            }
            var own = OwnLevels[ownLevel];
            var fr = new RectangleF(own.X * TS, own.Y * TS, own.Width * TS, own.Height * TS);
            g.FillRectangle(Carpet(CF.Index), fr);
            using (var vg = new LinearGradientBrush(new RectangleF(fr.X, fr.Y - 1, fr.Width, fr.Height + 2), Color.FromArgb(0, 0, 0, 0), Color.FromArgb(50, 0, 0, 0), 90f))
                g.FillRectangle(vg, fr);

            var wall = P(Color.FromArgb(24, 62, 118), 6);
            var trim = P(Color.FromArgb(150, Pal.Cyan), 1.3f);
            float L = fr.Left, R = fr.Right, T = fr.Top, Bt = fr.Bottom, d1 = 13 * TS, d2 = 15 * TS;
            g.DrawLine(wall, L, T + 3, R, T + 3); g.DrawLine(wall, L + 3, T, L + 3, Bt); g.DrawLine(wall, R - 3, T, R - 3, Bt);
            g.DrawLine(wall, L, Bt - 3, d1, Bt - 3); g.DrawLine(wall, d2, Bt - 3, R, Bt - 3);
            g.DrawLine(trim, L + 6, T + 6, R - 6, T + 6); g.DrawLine(trim, L + 6, T + 6, L + 6, Bt - 6); g.DrawLine(trim, R - 6, T + 6, R - 6, Bt - 6);
            g.DrawLine(trim, L + 6, Bt - 6, d1, Bt - 6); g.DrawLine(trim, d2, Bt - 6, R - 6, Bt - 6);

            DrawEscalator(g);

            // vchod (jen v přízemí)
            if (CF.Index > 0)
            {
                g.DrawLine(wall, d1, Bt - 3, d2, Bt - 3);
                g.DrawLine(trim, d1, Bt - 6, d2, Bt - 6);
            }
            var mat = new RectangleF(d1 + 3, 17 * TS + 3, 2 * TS - 6, TS - 6);
            if (CF.Index == 0)
            {
            FillRound(g, B(Color.FromArgb(128, 22, 40)), mat, 3);
            DrawRound(g, P(Pal.Gold, 1.4f), mat, 3);
            TxtC(g, "VSTUP", F(9, true), Pal.Cream, mat.X + mat.Width / 2, mat.Y + mat.Height / 2);
            g.FillRectangle(B(Pal.Gold), d1 - 2, Bt - 8, 4, 8); g.FillRectangle(B(Pal.Gold), d2 - 2, Bt - 8, 4, 8);
            }

            // nápis nahoře
            string sign = CF.Index == 0 ? "APEX KASINO" : "APEX KASINO · " + FloorNames[CF.Index].ToUpper();
            var sf = F(12, true);
            float sw = TextW(g, sign, sf) + 40;
            var plate = new RectangleF(fr.X + fr.Width / 2 - sw / 2, T - 1, sw, 12);
            if (own.Y > 0) plate.Y = T - 7;
            FillRound(g, B(Color.FromArgb(8, 20, 44)), plate, 4);
            DrawRound(g, P(Pal.Yellow, 1), plate, 4);
            DrawPyramid(g, plate.X + 13, plate.Y + 2, 12, 8);
            TxtC(g, sign, F(8.5f, true), Pal.Yellow, plate.X + plate.Width / 2 + 7, plate.Y + plate.Height / 2);
        }

        // eskalátor na polích 16–17 × 16–17; bez dalšího patra jen vyznačené místo
        void DrawEscalator(Graphics g)
        {
            var r = new RectangleF(16 * TS + 2, 16 * TS + 2, 2 * TS - 4, 2 * TS - 6);
            if (floors.Count < 2)
            {
                using (var dp = new Pen(Color.FromArgb(90, Pal.Muted), 1.2f) { DashStyle = DashStyle.Dash }) g.DrawRectangle(dp, r.X, r.Y, r.Width, r.Height);
                TxtC(g, "místo pro", F(7.5f, false), Color.FromArgb(150, Pal.Muted), r.X + r.Width / 2, r.Y + r.Height / 2 - 6);
                TxtC(g, "eskalátor", F(7.5f, true), Color.FromArgb(150, Pal.Muted), r.X + r.Width / 2, r.Y + r.Height / 2 + 5);
                return;
            }
            g.FillRectangle(B(95, Color.Black), r.X + 2, r.Y + 3, r.Width, r.Height);
            using (var br = new LinearGradientBrush(r, Color.FromArgb(150, 160, 175), Color.FromArgb(80, 90, 105), 90f)) g.FillRectangle(br, r);
            for (int i = 0; i < 9; i++) g.DrawLine(P(Color.FromArgb(60, 68, 82), 1.2f), r.X + 6, r.Y + 5 + i * 6.4f, r.Right - 6, r.Y + 5 + i * 6.4f);
            g.FillRectangle(B(Color.FromArgb(24, 26, 32)), r.X, r.Y, 5, r.Height);
            g.FillRectangle(B(Color.FromArgb(24, 26, 32)), r.Right - 5, r.Y, 5, r.Height);
            g.FillPolygon(B(Pal.Yellow), new[] { new PointF(r.X + r.Width / 2, r.Y + 14), new PointF(r.X + r.Width / 2 - 9, r.Y + 26), new PointF(r.X + r.Width / 2 + 9, r.Y + 26) });
            string lbl = CF.Index == 0 ? "PATRA" : "PŘÍZEMÍ";
            FillRound(g, B(230, Pal.Night), new RectangleF(r.X + 6, r.Bottom - 18, r.Width - 12, 13), 4);
            TxtC(g, lbl, F(7.5f, true), Pal.Cream, r.X + r.Width / 2, r.Bottom - 11.5f);
        }

        // ---------- dynamické části objektů ----------

        bool Blink(float hz) { return (int)(realT * hz) % 2 == 0; }

        void DrawDyn(Graphics g, Obj o)
        {
            switch (o.T.Id)
            {
                case "classic":
                case "pyramid":
                case "retro":
                case "clover":
                case "diamond":
                case "tower":
                    DrawScreen(g, SlotScreen(0, 0, ArtDown(o)), o, 0);
                    break;
                case "station":
                    {
                        var sc = StationScreens(ArtDown(o));
                        DrawScreen(g, sc[0], o, 0); DrawScreen(g, sc[1], o, 1);
                        break;
                    }
                case "multi":
                    {
                        var sc = MultiScreens(ArtDown(o));
                        for (int i = 0; i < 3; i++) DrawScreen(g, sc[i], o, i);
                        break;
                    }
                case "wheel":
                    {
                        var sc = WheelScreens(ArtDown(o));
                        DrawScreen(g, sc[0], o, 0); DrawScreen(g, sc[1], o, 1);
                        var c = WheelCenter(ArtDown(o));
                        float spin = Math.Max(o.Spin[0], o.Spin[1]);
                        float ang = o.Anim * 20 + (spin > 0 ? spin * 900 : 0);
                        Color[] wc = { Pal.Red, Pal.Yellow, Pal.Cyan, Color.White, Pal.Green, Color.FromArgb(150, 80, 220) };
                        var st = g.Save();
                        g.TranslateTransform(c.X, c.Y);
                        g.RotateTransform(ang);
                        for (int i = 0; i < 12; i++) g.FillPie(B(wc[i % wc.Length]), -9.5f, -9.5f, 19, 19, i * 30, 30);
                        g.FillEllipse(B(Pal.Gold), -2.5f, -2.5f, 5, 5);
                        g.Restore(st);
                        float py = ArtDown(o) ? c.Y - 11 : c.Y + 11;
                        g.FillPolygon(B(Color.White), new[] { new PointF(c.X - 2.5f, py), new PointF(c.X + 2.5f, py), new PointF(c.X, ArtDown(o) ? py + 5 : py - 5) });
                        break;
                    }
                case "island":
                    {
                        var sc = IslandScreens();
                        for (int i = 0; i < 4; i++) DrawScreen(g, sc[i], o, i);
                        var strip = new RectangleF(5, 27, 54, 10);
                        FillRound(g, B(Color.FromArgb(8, 8, 12)), strip, 3);
                        for (int i = 0; i < 12; i++)
                        {
                            bool on = ((int)(realT * 6) + i) % 3 == 0;
                            g.FillEllipse(B(on ? Pal.Yellow : Color.FromArgb(90, 70, 20)), strip.X + 2 + i * 4.4f, strip.Y - 1.6f, 2, 2);
                        }
                        string txt = Has("clover") ? FormatKc(pool) : "JACKPOT";
                        TxtC(g, txt, F(6.4f, true), Blink(2) || !Has("clover") ? Pal.Yellow : Pal.Cream, 32, 32.3f);
                        break;
                    }
                case "blackjack":
                    {
                        var spots = BjSpots();
                        bool any = false;
                        for (int i = 0; i < 3; i++)
                        {
                            if (!o.InUse(i)) continue;
                            any = true;
                            Card(g, spots[i].X - 5, spots[i].Y - 5, true, i);
                            Card(g, spots[i].X - 1, spots[i].Y - 4, true, i + 3);
                            Chips(g, spots[i].X + 5, spots[i].Y + 2, i);
                        }
                        if (any) { Card(g, 42, 18, true, 7); Card(g, 47, 18, (int)(o.Anim) % 3 != 0, 8); }
                        break;
                    }
                case "roulette":
                    {
                        bool any = o.UserCount > 0;
                        float ang = o.Anim * (any ? 160 : 12);
                        var st = g.Save();
                        g.TranslateTransform(26, 32);
                        g.RotateTransform(ang);
                        for (int i = 0; i < 18; i++)
                            g.FillPie(B(i == 0 ? Color.FromArgb(20, 150, 70) : i % 2 == 0 ? Color.FromArgb(200, 30, 40) : Color.FromArgb(22, 22, 26)), -17, -17, 34, 34, i * 20, 20);
                        g.FillEllipse(B(Color.FromArgb(120, 76, 36)), -10, -10, 20, 20);
                        g.DrawEllipse(P(Pal.Gold, 1), -10, -10, 20, 20);
                        g.DrawLine(P(Pal.Gold, 1.4f), -6, 0, 6, 0); g.DrawLine(P(Pal.Gold, 1.4f), 0, -6, 0, 6);
                        g.FillEllipse(B(Pal.Gold), -2.5f, -2.5f, 5, 5);
                        g.Restore(st);
                        if (any)
                        {
                            double ba = -o.Anim * 3.5;
                            g.FillEllipse(B(Color.White), 26 + (float)Math.Cos(ba) * 13.5f - 1.6f, 32 + (float)Math.Sin(ba) * 13.5f - 1.6f, 3.2f, 3.2f);
                        }
                        for (int i = 0; i < 6; i++) if (o.InUse(i)) Chips(g, 57 + (i % 3) * 10, i < 3 ? 22 : 40, i);
                        break;
                    }
                case "poker":
                    {
                        int n = 0;
                        for (int i = 0; i < 6; i++)
                        {
                            if (!o.InUse(i)) continue;
                            n++;
                            float x = 20 + (i % 3) * 28, y = i < 3 ? 13 : 45;
                            Card(g, x - 4, y - 3, false, i); Card(g, x + 1, y - 3, false, i);
                            Chips(g, x + 8, y - 1, i);
                        }
                        if (n >= 2) for (int k = 0; k < 5; k++) Card(g, 33 + k * 6.4f, 27, k < 3 || Blink(.5f), k + 10);
                        break;
                    }
                case "bar":
                    {
                        float x = 10 + ((float)Math.Sin(o.Anim * .7) + 1) / 2 * 76;
                        bool dn = ArtDown(o);
                        float y = dn ? 13.5f : 32 - 13.5f;
                        g.FillEllipse(B(Color.White), x - 5, y - 3.5f, 10, 7);
                        g.FillRectangle(B(Color.FromArgb(20, 20, 24)), x - 1.5f, y - 3.5f, 3, 7);
                        g.FillEllipse(B(Color.FromArgb(224, 172, 130)), x - 3, y - 3, 6, 6);
                        g.FillEllipse(B(Color.FromArgb(40, 28, 20)), x - 3, dn ? y - 3.4f : y - 1.6f, 6, 4.4f);
                        for (int i = 0; i < 3; i++)
                            if (o.InUse(i))
                            {
                                float gy = dn ? 22 : 10;
                                g.FillEllipse(B(170, Color.White), i * 32 + 13, gy - 3, 6, 6);
                                g.FillEllipse(B(Color.FromArgb(230, 150, 40)), i * 32 + 14.2f, gy - 1.8f, 3.6f, 3.6f);
                            }
                        break;
                    }
                case "atm":
                    {
                        var r = RY(ArtDown(o), 32, 0, 0, 9, 11, 14, 8);
                        int a = 90 + (int)(60 * Math.Sin(realT * 3 + o.X));
                        g.FillRectangle(B(a, Pal.Cyan), r);
                        g.FillRectangle(B(150, Color.White), r.X + 2, r.Y + 2, 7, 1); g.FillRectangle(B(110, Color.White), r.X + 2, r.Y + 4.5f, 10, 1);
                        break;
                    }
                case "led":
                    {
                        var st = g.Save();
                        g.SetClip(new RectangleF(4, 9, 56, 13), CombineMode.Intersect);
                        string msg = "VÍTEJTE V APEX KASINU  ·  NEXT LEVEL OF GAMING  ·  " + (Has("clover") ? "JACKPOT " + FormatKc(pool) + "  ·  " : "");
                        var f = F(8.5f, true);
                        float w = LedWidth(g, msg, f);
                        float x = 60 - (realT * 22 + o.X * 13) % (w + 20);
                        Txt(g, msg, f, Color.FromArgb(255, 170, 40), x, 9.5f);
                        Txt(g, msg, f, Color.FromArgb(255, 170, 40), x + w + 20, 9.5f);
                        g.Restore(st);
                        break;
                    }
                case "fountain":
                    for (int k = 0; k < 3; k++)
                    {
                        float ph = (realT * .5f + k / 3f) % 1;
                        float r = 9 + ph * 16;
                        g.DrawEllipse(P((int)((1 - ph) * 140), Color.White), 32 - r, 32 - r, r * 2, r * 2);
                    }
                    for (int k = 0; k < 8; k++)
                    {
                        double a = k * Math.PI / 4 + realT * .8;
                        float ph = (realT * 1.4f + k * .13f) % 1, rr = 4 + ph * 9;
                        g.FillEllipse(B((int)((1 - ph) * 220), Color.FromArgb(200, 235, 255)), 32 + (float)Math.Cos(a) * rr - 1, 32 + (float)Math.Sin(a) * rr - 1, 2, 2);
                    }
                    break;
                case "statue":
                    for (int k = 0; k < 3; k++)
                    {
                        float ph = (realT * .7f + k * .37f) % 1;
                        float x = 20 + (k * 11 + (int)(realT * .7f + k * .37f) * 7) % 26, y = 20 + (k * 7) % 22;
                        float s = (float)Math.Sin(ph * Math.PI) * 3.5f;
                        g.FillPolygon(B((int)(255 * Math.Sin(ph * Math.PI)), Color.White), new[] { new PointF(x, y - s), new PointF(x + s * .3f, y), new PointF(x, y + s), new PointF(x - s * .3f, y) });
                        g.FillPolygon(B((int)(255 * Math.Sin(ph * Math.PI)), Color.White), new[] { new PointF(x - s, y), new PointF(x, y - s * .3f), new PointF(x + s, y), new PointF(x, y + s * .3f) });
                    }
                    break;
            }
        }

        void DrawBroken(Graphics g, Obj o)
        {
            {
                var r = new RectangleF(0, 0, o.W * TS, o.H * TS);
                if (Blink(3)) DrawRound(g, P(Pal.Red, 2), r, 5);
                float bx = r.Width / 2, by = -6;
                g.FillEllipse(B(95, Color.Black), bx - 8, by - 6, 16, 16);
                g.FillEllipse(B(Pal.Red), bx - 8, by - 8, 16, 16);
                var wp = P(Color.White, 2.2f);
                g.DrawLine(wp, bx - 3.5f, by + 3.5f, bx + 2.5f, by - 2.5f);
                g.DrawEllipse(P(Color.White, 1.6f), bx + 1, by - 5.5f, 4.5f, 4.5f);
                if (o.Tech != null && o.Tech.Mode == 2)
                {
                    float k = 1 - Math.Max(0, o.Tech.Timer) / 3.5f;
                    var bar = new RectangleF(bx - 14, by + 11, 28, 4);
                    g.FillRectangle(B(200, Pal.Night), bar);
                    g.FillRectangle(B(Pal.Green), bar.X, bar.Y, bar.Width * k, bar.Height);
                }
            }
        }

        readonly Dictionary<string, float> ledW = new Dictionary<string, float>();
        float LedWidth(Graphics g, string s, Font f)
        {
            float w;
            if (!ledW.TryGetValue(s, out w)) { w = TextW(g, s, f); if (ledW.Count > 50) ledW.Clear(); ledW[s] = w; }
            return w;
        }

        void DrawScreen(Graphics g, RectangleF r, Obj o, int seat)
        {
            if (o.Broken)
            {
                g.FillRectangle(B(Blink(3) ? Color.FromArgb(90, 10, 16) : Color.FromArgb(20, 4, 6)), r);
                TxtC(g, "!", F(8, true), Color.FromArgb(255, 120, 120), r.X + r.Width / 2, r.Y + r.Height / 2);
                return;
            }
            float cw = (r.Width - 2) / 3f;
            float spin = seat < o.Spin.Length ? o.Spin[seat] : 0;
            for (int k = 0; k < 3; k++)
            {
                var c = new RectangleF(r.X + 1 + k * cw + .3f, r.Y + 1, cw - .6f, r.Height - 2);
                int s = spin > (2 - k) * .2f ? (int)((realT * 22 + k * 7 + seat * 3 + o.X) % 5) : o.Reels[seat * 3 + k];
                DrawSym(g, s, c);
            }
            if (!o.InUse(seat)) g.FillRectangle(B(125, Color.FromArgb(4, 8, 18)), r);
            else if (spin <= 0 && o.Reels[seat * 3] == o.Reels[seat * 3 + 1] && o.Reels[seat * 3 + 1] == o.Reels[seat * 3 + 2] && Blink(4))
                g.DrawRectangle(P(Pal.Yellow, 1), r.X, r.Y, r.Width, r.Height);
        }

        void Card(Graphics g, float x, float y, bool face, int seed)
        {
            g.FillRectangle(B(90, Color.Black), x + .6f, y + .8f, 5, 7);
            if (face)
            {
                g.FillRectangle(B(Color.White), x, y, 5, 7);
                g.FillEllipse(B(seed % 2 == 0 ? Color.FromArgb(210, 30, 40) : Color.FromArgb(20, 20, 24)), x + 1.4f, y + 2.2f, 2.2f, 2.2f);
            }
            else
            {
                g.FillRectangle(B(Pal.Navy), x, y, 5, 7);
                g.DrawRectangle(P(Pal.Cream, .5f), x + .7f, y + .7f, 3.6f, 5.6f);
            }
        }

        void Chips(Graphics g, float x, float y, int seed)
        {
            Color[] cs = { Pal.Red, Pal.Yellow, Pal.Cyan, Color.White, Pal.Green };
            for (int k = 0; k < 3; k++)
            {
                g.FillEllipse(B(cs[(seed + k) % cs.Length]), x, y - k * 1.3f, 4.5f, 3);
                g.DrawEllipse(P(90, Color.Black), x, y - k * 1.3f, 4.5f, 3);
            }
        }

        // ---------- lidé ----------

        PointF SeatPos(Agent a)
        {
            float x = a.X * TS, y = a.Y * TS;
            var gu = a as Guest;
            if (gu != null && gu.State == GS.Use && gu.Target != null) { x += gu.FaceX * 7; y += gu.FaceY * 7; }
            return new PointF(x, y);
        }

        Pen P(int alpha, Color c) { return P(Color.FromArgb(alpha, c), 1); }

        void Person(Graphics g, float x, float y, float fx, float fy, float walk, Color body, Color skin, Color hair, bool moving)
        {
            float bob = moving ? (float)Math.Sin(walk) * .9f : 0;
            g.FillEllipse(B(80, Color.Black), x - 7, y - 2, 14, 8);
            y += bob;
            g.FillEllipse(B(body), x - 7, y - 7, 14, 11);
            g.FillEllipse(B(40, Color.White), x - 5, y - 6.5f, 7, 4);
            float hx = x + fx * 1.5f, hy = y - 5 + fy * 1.5f;
            g.FillEllipse(B(skin), hx - 4.5f, hy - 4.5f, 9, 9);
            float ang = (float)(Math.Atan2(fy, fx) * 180 / Math.PI);
            g.FillPie(B(hair), hx - 4.6f, hy - 4.6f, 9.2f, 9.2f, ang + 90, 180);
        }

        void DrawGuest(Graphics g, Guest gu)
        {
            var p = SeatPos(gu);
            bool moving = gu.State != GS.Use;
            Person(g, p.X, p.Y, gu.FaceX, gu.FaceY, gu.Walk, gu.Shirt, gu.Skin, gu.Hair, moving);
            if (gu.Vip) g.DrawEllipse(P(Pal.Gold, 1.3f), p.X - 7.5f, p.Y - 7.5f, 15, 12);
        }

        void DrawStaff(Graphics g, Staff s)
        {
            var p = SeatPos(s);
            Color body = s.Role == 0 ? Pal.Yellow : s.Role == 1 ? Color.FromArgb(40, 160, 90) : Color.FromArgb(24, 26, 32);
            Color hair = s.Role == 0 ? Pal.Navy : s.Role == 1 ? Color.FromArgb(60, 40, 30) : Color.FromArgb(20, 20, 20);
            Person(g, p.X, p.Y, s.FaceX, s.FaceY, s.Walk, body, Color.FromArgb(230, 190, 150), hair, s.Mode == 1);
            if (s.Role == 0) { g.DrawLine(P(Color.FromArgb(220, 225, 235), 1.4f), p.X - 6, p.Y - 2, p.X + 6, p.Y - 2); if (s.Mode == 2) g.DrawLine(P(Color.FromArgb(180, 190, 200), 2), p.X + 5, p.Y - 3, p.X + 10, p.Y - 8 + (float)Math.Sin(realT * 14) * 2); }
            if (s.Role == 1) { float sw = s.Mode == 2 ? (float)Math.Sin(realT * 12) * 4 : 0; g.DrawLine(P(Color.FromArgb(150, 110, 60), 1.6f), p.X + 5, p.Y - 4, p.X + 9 + sw, p.Y + 5); g.FillEllipse(B(Color.FromArgb(200, 180, 120)), p.X + 7 + sw, p.Y + 3, 5, 3); }
            if (s.Role == 2) { g.FillRectangle(B(Color.White), p.X - 1, p.Y - 6, 2, 4); g.FillEllipse(B(Color.FromArgb(40, 40, 40)), p.X + 3, p.Y - 10, 2.5f, 2.5f); }
        }

        void DrawBubble(Graphics g, Guest gu)
        {
            int icon = -1;
            if (gu.ThoughtT > 0 && gu.Icon >= 0) icon = gu.Icon;
            else if (gu.State != GS.Use)
            {
                if (gu.Bladder > 75) icon = 1; else if (gu.Thirst > 75) icon = 0; else if (gu.Energy < 25) icon = 4;
            }
            if (icon < 0) return;
            var p = SeatPos(gu);
            float x = p.X + 6, y = p.Y - 20;
            g.FillEllipse(B(220, Color.White), x - 6, y - 6, 12, 12);
            g.FillPolygon(B(220, Color.White), new[] { new PointF(x - 3, y + 4), new PointF(x - 7, y + 9), new PointF(x + 1, y + 5) });
            switch (icon)
            {
                case 0:
                    g.FillEllipse(B(Pal.Cyan), x - 3, y - 1.5f, 6, 6);
                    g.FillPolygon(B(Pal.Cyan), new[] { new PointF(x, y - 5), new PointF(x - 3, y + .5f), new PointF(x + 3, y + .5f) });
                    break;
                case 1: TxtC(g, "WC", F(5.8f, true), Pal.Navy, x, y); break;
                case 2: TxtC(g, "!", F(9, true), Pal.Red, x, y); break;
                case 3:
                    g.FillEllipse(B(Pal.Red), x - 4, y - 3.5f, 4.4f, 4.4f); g.FillEllipse(B(Pal.Red), x - .4f, y - 3.5f, 4.4f, 4.4f);
                    g.FillPolygon(B(Pal.Red), new[] { new PointF(x - 3.9f, y - .6f), new PointF(x + 3.9f, y - .6f), new PointF(x, y + 3.8f) });
                    break;
                case 4: TxtC(g, "z", F(8, true), Pal.Dim, x, y - .5f); break;
            }
        }

        // ---------- stavěcí náhled ----------

        void DrawGhost(Graphics g)
        {
            int x = GhostX(), y = GhostY();
            string err = CanBuild(tool, x, y, toolDir);
            var gd = Dims(tool, toolDir);
            var r = new RectangleF(x * TS, y * TS, gd.Width * TS, gd.Height * TS);
            var bmp = Sprite(tool, toolDir);
            var m = g.Transform;
            g.ResetTransform();
            using (var ia = new ImageAttributes())
            {
                var cm = new ColorMatrix { Matrix33 = .72f };
                ia.SetColorMatrix(cm);
                float dx = ox + (wx0 + (x * TS - Pad) * wz) * scale, dy = oy + (wy0 + (y * TS - Pad) * wz) * scale;
                g.DrawImage(bmp, new Rectangle((int)Math.Round(dx), (int)Math.Round(dy), bmp.Width, bmp.Height), 0, 0, bmp.Width, bmp.Height, GraphicsUnit.Pixel, ia);
            }
            g.Transform = m;
            m.Dispose();
            Color c = err == null ? Pal.Green : Pal.Red;
            g.FillRectangle(B(55, c), r);
            DrawRound(g, P(c, 1.6f), r, 3);
            foreach (var s in SeatsFor(tool, x, y, toolDir))
            {
                bool ok = InGrid(s.X, s.Y) && Walkable(s.X, s.Y);
                g.FillEllipse(B(ok ? 130 : 90, ok ? Pal.Cyan : Pal.Red), s.X * TS + 10, s.Y * TS + 10, 12, 12);
            }
            string label = err ?? (carry != null ? "Položit sem" : FormatKc(CostOf(tool)));
            var f = F(10, true);
            float w = TextW(g, label, f) + 14;
            var tag = new RectangleF(r.X + r.Width / 2 - w / 2, r.Bottom + 4, w, 17);
            if (tag.Bottom > GH * TS - 2) tag.Y = r.Y - 21;
            FillRound(g, B(230, Pal.Night), tag, 8);
            TxtC(g, label, f, err == null ? Pal.Cream : Color.FromArgb(255, 150, 150), tag.X + tag.Width / 2, tag.Y + tag.Height / 2);
        }
    }
}
