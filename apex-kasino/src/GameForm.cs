using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Text;
using System.Runtime.InteropServices;
using System.Windows.Forms;

namespace ApexKasino
{
    static class Program
    {
        [DllImport("user32.dll")]
        static extern bool SetProcessDPIAware();

        [STAThread]
        static void Main()
        {
            try { SetProcessDPIAware(); } catch { }
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new GameForm());
        }
    }

    enum Screen { Title, Play, Menu, Help }

    partial class GameForm : Form
    {
        const float VW = 1280, VH = 760, MX = 16, MY = 60, TS = 32;
        static readonly int[] Speeds = { 0, 1, 2, 4 };

        Screen screen = Screen.Title;
        Screen helpBack = Screen.Title;
        int speedIdx = 1, lastSpeed = 1;
        readonly Timer timer = new Timer();
        readonly Stopwatch clock = new Stopwatch();
        double lastT;
        float realT;

        float scale = 1, ox, oy;
        PointF mouse;
        bool shiftDown;

        ObjType tool; int toolDir; bool sellTool, moveTool, moodMap;
        Obj pressObj; PointF pressPos; bool mouseDown;
        Obj sel; Guest selGuest; Staff selStaff;
        int tab; Cat cat = Cat.Automaty;
        string hoverTip, flashErr; float flashErrT;

        List<Btn> btns = new List<Btn>(), btnsPrev = new List<Btn>();
        readonly List<Particle> parts = new List<Particle>();
        readonly List<FloatText> texts = new List<FloatText>();

        public GameForm()
        {
            Text = "APEX Kasino";
            BackColor = Pal.Night;
            StartPosition = FormStartPosition.CenterScreen;
            KeyPreview = true;
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true);

            float s;
            using (var g = CreateGraphics()) s = g.DpiX / 96f;
            var wa = Screen_WorkingArea();
            s = Math.Min(s, Math.Min((wa.Width - 40) / VW, (wa.Height - 80) / VH));
            ClientSize = new Size((int)(VW * s), (int)(VH * s));
            MinimumSize = new Size(800, 520);

            try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { Icon = MakeIcon(); }
            InitSounds();
            NewGame(true);

            timer.Interval = 15;
            timer.Tick += Tick;
            clock.Start();
            timer.Start();
        }

        bool OnTitle { get { return screen == Screen.Title || (screen == Screen.Help && helpBack == Screen.Title); } }

        static Rectangle Screen_WorkingArea() { return System.Windows.Forms.Screen.PrimaryScreen.WorkingArea; }

        void Tick(object sender, EventArgs e)
        {
            double now = clock.Elapsed.TotalSeconds;
            float dt = (float)Math.Min(.05, now - lastT);
            lastT = now;
            realT += dt;
            if (OnTitle) Step(dt);
            else if (screen == Screen.Play && activeEvent == null)
            {
                int n = Speeds[speedIdx];
                for (int i = 0; i < n; i++) Step(dt);
            }
            UpdateFx(dt, screen == Screen.Title || (screen == Screen.Play && speedIdx > 0));
            Invalidate();
        }

        void UpdateFx(float dt, bool running)
        {
            float k = running ? Math.Max(1, Speeds[speedIdx]) : 0;
            if (screen == Screen.Title) k = 1;
            for (int i = parts.Count - 1; i >= 0; i--)
            {
                var p = parts[i];
                p.X += p.VX * dt; p.Y += p.VY * dt; p.VY += 9 * dt; p.Life -= dt;
                if (p.Life <= 0) parts.RemoveAt(i);
            }
            for (int i = texts.Count - 1; i >= 0; i--)
            {
                var t = texts[i];
                t.Y -= .8f * dt; t.Life -= dt;
                if (t.Life <= 0) texts.RemoveAt(i);
            }
            if (bannerT > 0) bannerT -= dt;
            if (reportT > 0) reportT -= dt;
            if (flashErrT > 0) flashErrT -= dt;
        }

        // efekty jsou v souřadnicích mřížky (pole)
        void Float(float x, float y, string s, Color c) { if (CF != ViewF) return; texts.Add(new FloatText { X = x, Y = y, T = s, C = c, Life = 1.8f }); }

        void Confetti(float x, float y, int n)
        {
            if (CF != ViewF) return;
            Color[] cs = { Pal.Yellow, Pal.Cream, Pal.Cyan, Pal.Red, Color.White, Pal.Green };
            for (int i = 0; i < n; i++)
            {
                double a = rng.NextDouble() * Math.PI * 2; float v = (float)rng.NextDouble() * 4 + 1;
                parts.Add(new Particle { X = x, Y = y, VX = (float)Math.Cos(a) * v, VY = (float)Math.Sin(a) * v - 4, Life = 1 + (float)rng.NextDouble(), Size = 2 + (float)rng.NextDouble() * 3, C = cs[i % cs.Length] });
            }
        }

        void Coins(float x, float y, int n)
        {
            if (CF != ViewF) return;
            for (int i = 0; i < n; i++)
            {
                double a = -Math.PI / 2 + (rng.NextDouble() - .5) * 1.6; float v = (float)rng.NextDouble() * 3 + 2;
                parts.Add(new Particle { X = x, Y = y, VX = (float)Math.Cos(a) * v, VY = (float)Math.Sin(a) * v, Life = .8f + (float)rng.NextDouble() * .4f, Size = 4, C = Pal.Yellow, Coin = true });
            }
        }

        void Dust(float x, float y, float w, float h)
        {
            if (CF != ViewF) return;
            for (int i = 0; i < 16; i++)
                parts.Add(new Particle
                {
                    X = x + (float)rng.NextDouble() * w, Y = y + (float)rng.NextDouble() * h,
                    VX = (float)(rng.NextDouble() - .5) * 2, VY = -(float)rng.NextDouble() * 2, Life = .5f + (float)rng.NextDouble() * .3f,
                    Size = 2 + (float)rng.NextDouble() * 2, C = Color.FromArgb(200, 210, 225)
                });
        }

        void ClearSelection() { sel = null; selGuest = null; selStaff = null; }

        void SetView(int i)
        {
            CancelCarry();
            ClearSelection();
            viewFloor = i; CF = ViewF;
            floorDirty = true;
            parts.Clear(); texts.Clear();
        }

        protected override void OnMouseWheel(MouseEventArgs e)
        {
            mouse = ToLogical(e.Location);
            if (tab == 0 && new RectangleF(936, 138, 320, 336).Contains(mouse)) buildScroll -= Math.Sign(e.Delta) * 66;
        }

        float buildScroll;

        // ---------- vstup ----------

        PointF ToLogical(Point p) { return new PointF((p.X - ox) / scale, (p.Y - oy) / scale); }

        bool InMap(PointF p) { return p.X >= MX && p.Y >= MY && p.X < MX + GW * TS && p.Y < MY + GH * TS; }

        int GhostX() { return (int)Math.Floor(MouseWX - Dims(tool, toolDir).Width / 2f + .5f); }
        int GhostY() { return (int)Math.Floor(MouseWY - Dims(tool, toolDir).Height / 2f + .5f); }

        protected override void OnMouseMove(MouseEventArgs e)
        {
            mouse = ToLogical(e.Location);
            // přetažení objektu myší
            if (mouseDown && pressObj != null && carry == null && screen == Screen.Play && activeEvent == null
                && Dist(mouse.X, mouse.Y, pressPos.X, pressPos.Y) > 8 && objs.Contains(pressObj))
            {
                PickUp(pressObj);
                pressObj = null;
            }
        }

        protected override void OnMouseUp(MouseEventArgs e)
        {
            mouse = ToLogical(e.Location);
            if (e.Button != MouseButtons.Left) return;
            bool wasDown = mouseDown;
            mouseDown = false;
            pressObj = null;
            // puštění přetahovaného objektu
            if (wasDown && carry != null && dragging && InMap(mouse)) DropAt(GhostX(), GhostY(), toolDir);
            dragging = false;
        }

        bool dragging;

        protected override void OnMouseDown(MouseEventArgs e)
        {
            mouse = ToLogical(e.Location);
            if (e.Button == MouseButtons.Right)
            {
                if (carry != null) CancelCarry();
                else if (tool != null || sellTool || moveTool) { tool = null; sellTool = false; moveTool = false; }
                else ClearSelection();
                return;
            }
            if (e.Button != MouseButtons.Left) return;
            mouseDown = true; dragging = false;
            for (int i = btnsPrev.Count - 1; i >= 0; i--)
            {
                if (btnsPrev[i].R.Contains(mouse))
                {
                    Sfx(sClick);
                    btnsPrev[i].A();
                    return;
                }
            }
            if (screen == Screen.Play && activeEvent == null && InMap(mouse)) MapClick();
        }

        void MapClick()
        {
            float wx = MouseWX, wy = MouseWY;
            int tx = (int)wx, ty = (int)wy;
            if (carry != null) { DropAt(GhostX(), GhostY(), toolDir); return; }
            if (tool != null)
            {
                int x = GhostX(), y = GhostY();
                string err = CanBuild(tool, x, y, toolDir);
                if (err == null)
                {
                    var o = Place(tool, x, y, toolDir, false);
                    Dust(o.X, o.Y, o.W, o.H);
                    Float(o.X + o.W / 2f, o.Y, "−" + FormatKc(CostOf(o.T)), Pal.Muted);
                    Sfx(sPlace);
                }
                else { flashErr = err; flashErrT = 2; Sfx(sErr); }
                return;
            }
            var hit = InGrid(tx, ty) ? occ[tx, ty] : null;
            if (moveTool)
            {
                if (hit != null) PickUp(hit);
                return;
            }
            if (sellTool)
            {
                if (hit != null)
                {
                    Float(hit.X + hit.W / 2f, hit.Y, "+" + FormatKc(hit.T.Cost / 2), Pal.Green);
                    Dust(hit.X, hit.Y, hit.W, hit.H);
                    Sell(hit); Sfx(sSell);
                }
                return;
            }
            ClearSelection();
            float bd = .55f;
            foreach (var g in guests)
            {
                if (g.Hidden) continue;
                float d = Dist(g.X, g.Y - .15f, wx, wy);
                if (d < bd) { bd = d; selGuest = g; }
            }
            foreach (var s in staff)
            {
                float d = Dist(s.X, s.Y - .15f, wx, wy);
                if (d < bd) { bd = d; selStaff = s; selGuest = null; }
            }
            if (selGuest == null && selStaff == null)
            {
                sel = hit;
                if (hit != null) { pressObj = hit; pressPos = mouse; dragging = true; }
            }
        }

        static float Dist(float ax, float ay, float bx, float by) { float dx = ax - bx, dy = ay - by; return (float)Math.Sqrt(dx * dx + dy * dy); }

        protected override bool ProcessCmdKey(ref Message msg, Keys keyData)
        {
            if (keyData == Keys.Space || keyData == Keys.Escape || keyData == Keys.Delete) { HandleKey(keyData); return true; }
            return base.ProcessCmdKey(ref msg, keyData);
        }

        protected override void OnKeyDown(KeyEventArgs e)
        {
            shiftDown = e.Shift;
            HandleKey(e.KeyCode);
            e.Handled = true;
        }

        protected override void OnKeyUp(KeyEventArgs e) { shiftDown = e.Shift; }

        void HandleKey(Keys k)
        {
            if (k == Keys.M) { muted = !muted; return; }
            if (screen == Screen.Help) { if (k == Keys.Escape || k == Keys.Enter) screen = helpBack; return; }
            if (screen == Screen.Menu) { if (k == Keys.Escape) screen = Screen.Play; return; }
            if (screen == Screen.Title)
            {
                if (k == Keys.Enter) StartNew();
                return;
            }
            if (bankrupt || activeEvent != null) return;
            switch (k)
            {
                case Keys.Escape:
                    if (carry != null) CancelCarry();
                    else if (tool != null || sellTool || moveTool) { tool = null; sellTool = false; moveTool = false; }
                    else if (sel != null || selGuest != null || selStaff != null) ClearSelection();
                    else screen = Screen.Menu;
                    break;
                case Keys.Space:
                    if (speedIdx == 0) speedIdx = lastSpeed; else { lastSpeed = speedIdx; speedIdx = 0; }
                    break;
                case Keys.D1: case Keys.NumPad1: speedIdx = 1; break;
                case Keys.D2: case Keys.NumPad2: speedIdx = 2; break;
                case Keys.D3: case Keys.NumPad3: speedIdx = 3; break;
                case Keys.R:
                    if (tool != null && tool.Rot) toolDir = (toolDir + 1) % 4;
                    else if (sel != null && sel.T.Rot && Rotate(sel)) Sfx(sPlace);
                    break;
                case Keys.Delete:
                    if (sel != null) { Float(sel.X + sel.W / 2f, sel.Y, "+" + FormatKc(sel.T.Cost / 2), Pal.Green); Sell(sel); Sfx(sSell); }
                    else { CancelCarry(); sellTool = !sellTool; tool = null; moveTool = false; }
                    break;
                case Keys.X: CancelCarry(); sellTool = !sellTool; tool = null; moveTool = false; break;
                case Keys.V:
                    if (sel != null) PickUp(sel);
                    else { CancelCarry(); moveTool = !moveTool; tool = null; sellTool = false; }
                    break;
                case Keys.N: moodMap = !moodMap; break;
                case Keys.PageUp: if (viewFloor + 1 < floors.Count) SetView(viewFloor + 1); break;
                case Keys.PageDown: if (viewFloor > 0) SetView(viewFloor - 1); break;
                case Keys.L: tab = 5; break;
                case Keys.F5: Save(false); Sfx(sPlace); break;
                case Keys.F9: if (HasSave()) LoadGame(); break;
                case Keys.B: tab = 0; break;
                case Keys.P: tab = 1; break;
                case Keys.U: tab = 2; break;
                case Keys.F: tab = 3; break;
                case Keys.C: tab = 4; break;
            }
        }

        protected override void OnDeactivate(EventArgs e)
        {
            shiftDown = false;
            base.OnDeactivate(e);
        }

        protected override void OnFormClosing(FormClosingEventArgs e)
        {
            CancelCarry();
            if (!demo && screen != Screen.Title && !bankrupt) Save(true);
            base.OnFormClosing(e);
        }

        void StartNew()
        {
            NewGame(false);
            screen = Screen.Play; speedIdx = 1; tab = 0; cat = Cat.Automaty;
            parts.Clear(); texts.Clear();
            Sfx(sGoal);
        }

        void ContinueGame()
        {
            if (!HasSave()) return;
            if (LoadGame()) { screen = Screen.Play; speedIdx = 1; parts.Clear(); texts.Clear(); }
        }

        void ToTitle()
        {
            if (!demo && !bankrupt) Save(true);
            NewGame(true);
            screen = Screen.Title;
            parts.Clear(); texts.Clear();
        }
    }
}
