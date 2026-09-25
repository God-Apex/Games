using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;

namespace ApexKasino
{
    // panely, tlačítka a překryvná okna
    partial class GameForm
    {
        // styl: 0 běžné, 1 hlavní (žluté), 2 aktivní záložka, 3 nebezpečné
        bool Button(Graphics g, RectangleF r, string text, Action a, int style, bool enabled)
        {
            bool hover = enabled && r.Contains(mouse);
            Color bg, fg;
            switch (style)
            {
                case 1: bg = hover ? Pal.Cream : Pal.Yellow; fg = Pal.Ink; break;
                case 2: bg = Pal.Panel3; fg = Pal.Yellow; break;
                case 3: bg = hover ? Color.FromArgb(150, 36, 46) : Color.FromArgb(110, 26, 36); fg = Color.White; break;
                default: bg = hover ? Pal.Panel3 : Pal.Panel2; fg = Pal.Text; break;
            }
            if (!enabled) { bg = Color.FromArgb(14, 30, 56); fg = Pal.Dim; }
            FillRound(g, B(bg), r, 6);
            if (style == 0 && enabled) DrawRound(g, P(Pal.Line, 1), r, 6);
            if (style == 2) g.FillRectangle(B(Pal.Yellow), r.X + 8, r.Bottom - 3, r.Width - 16, 2);
            if (text != null) TxtC(g, text, F(r.Height > 30 ? 14 : 12, true), fg, r.X + r.Width / 2, r.Y + r.Height / 2);
            if (enabled && a != null) btns.Add(new Btn { R = r, A = a });
            return hover;
        }

        void Label(Graphics g, string s, float x, float y) { Txt(g, s, F(9.5f, true), Pal.Muted, x, y); }

        void Card(Graphics g, RectangleF r) { FillRound(g, B(Pal.Panel), r, 10); DrawRound(g, P(Pal.Line, 1), r, 10); }

        // ---------- horní lišta ----------

        void DrawTopBar(Graphics g)
        {
            g.FillRectangle(B(Pal.Night), 0, 0, VW, 52);
            using (var lg = new LinearGradientBrush(new RectangleF(0, 51, VW, 2), Pal.Navy, Pal.Cyan, 0f)) g.FillRectangle(lg, 0, 51, VW, 2);
            DrawPyramid(g, 34, 11, 36, 29);
            Txt(g, "APEX", F(23, true), Color.White, 56, 8);
            Txt(g, "KASINO", F(10, true), Pal.Yellow, 122, 21);

            Label(g, "PENÍZE", 200, 7);
            Txt(g, FormatKc(money), F(19, true), money >= 0 ? Color.White : Pal.Red, 197, 19);
            Label(g, "DEN " + day, 372, 7);
            Txt(g, TimeStr(), F(19, true), Color.White, 369, 19);
            Label(g, "HOSTÉ", 452, 7);
            Txt(g, guests.Count.ToString(), F(19, true), Color.White, 449, 19);

            Label(g, "HODNOCENÍ", 522, 7);
            int st = StarsNow();
            for (int i = 0; i < 5; i++) DrawStar(g, 531 + i * 19, 34, 8.5f, i < st ? Pal.Yellow : Color.FromArgb(34, 56, 90));
            Txt(g, leftCount < 8 ? "nové" : ((int)rating) + " %", F(10.5f, false), Pal.Muted, 624, 27);
            if (new RectangleF(518, 2, 150, 48).Contains(mouse))
                hoverTip = "Hodnocení kasina: " + st + " " + StarWord(st) + ". Procenta ukazují spokojenost odcházejících hostů. Na vyšší hodnocení potřebuješ i vybavení – seznam je v záložce Cíle.";

            // rychlost
            Label(g, "RYCHLOST", 682, 7);
            for (int i = 0; i < 4; i++)
            {
                int k = i;
                var r = new RectangleF(682 + i * 38, 20, 34, 25);
                Button(g, r, null, () => { if (k > 0) lastSpeed = k; speedIdx = k; }, speedIdx == i ? 1 : 0, true);
                Color c = speedIdx == i ? Pal.Ink : Pal.Text;
                float cx = r.X + r.Width / 2, cy = r.Y + r.Height / 2;
                if (i == 0) { g.FillRectangle(B(c), cx - 5, cy - 6, 3.5f, 12); g.FillRectangle(B(c), cx + 1.5f, cy - 6, 3.5f, 12); }
                else
                {
                    int n = i == 3 ? 3 : i;
                    float w = 7, start = cx - n * w / 2;
                    for (int j = 0; j < n; j++) g.FillPolygon(B(c), new[] { new PointF(start + j * w, cy - 6), new PointF(start + j * w + w, cy), new PointF(start + j * w, cy + 6) });
                }
            }

            if (Has("clover"))
            {
                Label(g, "CLOVER LINK JACKPOT", 850, 7);
                Txt(g, FormatKc(pool), F(18, true), Pal.Yellow, 847, 19);
            }
            else
            {
                Label(g, "HODNOTA KASINA", 850, 7);
                Txt(g, FormatKc(CasinoValue()), F(18, true), Color.White, 847, 19);
            }

            Button(g, new RectangleF(1170, 11, 94, 30), "Menu", () => { screen = Screen.Menu; }, 0, true);
        }

        // ---------- pravý panel ----------

        static readonly string[] TabNames = { "Stavět", "Personál", "Vylepš.", "Finance", "Cíle", "Vedení" };

        void DrawRightPanel(Graphics g)
        {
            var panel = new RectangleF(928, 60, 336, 684);
            Card(g, panel);
            for (int i = 0; i < 6; i++)
            {
                int k = i;
                Button(g, new RectangleF(934 + i * 54.3f, 66, 52.3f, 30), TabNames[i], () => { tab = k; }, tab == i ? 2 : 0, true);
            }
            switch (tab)
            {
                case 0: DrawBuildTab(g); break;
                case 1: DrawStaffTab(g); break;
                case 2: DrawUpgradesTab(g); break;
                case 3: DrawFinanceTab(g); break;
                case 4: DrawGoalsTab(g); break;
                case 5: DrawTeamTab(g); break;
            }
            DrawGoalCard(g, new RectangleF(936, 654, 320, 82));
        }

        static readonly string[] CatNames = { "Automaty", "Stoly", "Služby", "Dekorace" };
        static readonly string[] CatTips = {
            "Automaty jsou hlavní zdroj příjmů. Nech před nimi volné pole – tam sedí hráč. R otočí automat.",
            "Ke stolům chodí bohatší hosté a sázejí víc. Mzda krupiéra je v údržbě stolu.",
            "Bez toalet a baru hosté rychle odcházejí a kazí hodnocení. Koš omezí odpadky.",
            "Dekorace zvedají náladu hostů v okruhu 4 polí a lákají do kasina nové hosty."
        };

        void DrawBuildTab(Graphics g)
        {
            for (int i = 0; i < 4; i++)
            {
                var c = (Cat)i;
                Button(g, new RectangleF(936 + i * 80.5f, 104, 78, 26), CatNames[i], () => { cat = c; buildScroll = 0; }, cat == c ? 2 : 0, true);
            }
            // seznam se posouvá kolečkem myši
            var list = new RectangleF(936, 138, 320, 336);
            int count = 0; foreach (var t in Catalog.All) if (t.Cat == cat) count++;
            float maxScroll = Math.Max(0, count * 66 - 6 - list.Height);
            buildScroll = Math.Max(0, Math.Min(maxScroll, buildScroll));
            var clip = g.Save();
            g.SetClip(list, System.Drawing.Drawing2D.CombineMode.Intersect);
            float y = 138 - buildScroll;
            foreach (var t in Catalog.All)
            {
                if (t.Cat != cat) continue;
                var r = new RectangleF(936, y, 320, 60);
                if (r.Bottom < list.Top || r.Top > list.Bottom) { y += 66; continue; }
                bool locked = t.Stars > maxStars;
                bool active = tool == t;
                bool hover = r.Contains(mouse);
                FillRound(g, B(active ? Color.FromArgb(60, 60, 30) : hover && !locked ? Pal.Panel3 : Pal.Panel2), r, 8);
                if (active) DrawRound(g, P(Pal.Yellow, 1.6f), r, 8);
                var ib = new RectangleF(942, y + 6, 48, 48);
                FillRound(g, B(Color.FromArgb(4, 14, 32)), ib, 6);
                DrawIcon(g, t, ib);
                Txt(g, t.Name, F(13, true), locked ? Pal.Dim : Color.White, 998, y + 6);
                int cost = CostOf(t);
                TxtR(g, FormatKc(cost), F(12.5f, true), locked ? Pal.Dim : money >= cost ? Pal.Yellow : Pal.Red, 1250, y + 7);
                if (cost < t.Cost && !locked) TxtR(g, "sleva 30 %", F(9, true), Pal.Green, 1250, y + 24);
                Txt(g, StatLine(t), F(10.5f, false), locked ? Pal.Dim : Pal.Muted, 998, y + 25);
                Txt(g, t.W + "×" + t.H + " · údržba " + FormatKc(t.Upkeep) + "/den" + (t.Attract > 0 ? " · atraktivita +" + t.Attract : ""), F(9.5f, false), Pal.Dim, 998, y + 40);
                if (locked)
                {
                    FillRound(g, B(150, Pal.Night), r, 8);
                    DrawStar(g, 1190, y + 30, 7, Pal.Yellow);
                    Txt(g, "od " + t.Stars + " " + StarWord(t.Stars), F(11, true), Pal.Cream, 1200, y + 22);
                }
                hover = hover && list.Contains(mouse);
                if (hover) hoverTip = t.Name + ": " + t.Desc;
                var tt = t;
                var hit = RectangleF.Intersect(r, list);
                if (!locked && hit.Height > 4) btns.Add(new Btn { R = hit, A = () => { CancelCarry(); tool = tool == tt ? null : tt; toolDir = 0; sellTool = false; moveTool = false; ClearSelection(); } });
                y += 66;
            }
            g.Restore(clip);
            if (maxScroll > 0)
            {
                float th = list.Height * list.Height / (list.Height + maxScroll);
                float ty = list.Y + (list.Height - th) * buildScroll / maxScroll;
                FillRound(g, B(Pal.Line), new RectangleF(1259, list.Y, 3, list.Height), 1.5f);
                FillRound(g, B(Pal.Muted), new RectangleF(1259, ty, 3, th), 1.5f);
                if (buildScroll < maxScroll) TxtC(g, "kolečkem myši další", F(9, false), Pal.Dim, 1096, list.Bottom + 5);
            }
            y = 486;
            Button(g, new RectangleF(936, y, 77, 30), "Přesun (V)", () => { CancelCarry(); moveTool = !moveTool; tool = null; sellTool = false; }, moveTool || carry != null ? 2 : 0, true);
            Button(g, new RectangleF(1017, y, 77, 30), "Otočit (R)", () => { toolDir = (toolDir + 1) % 4; }, 0, tool != null && tool.Rot);
            Button(g, new RectangleF(1098, y, 77, 30), "Prodat (X)", () => { CancelCarry(); sellTool = !sellTool; tool = null; moveTool = false; }, sellTool ? 3 : 0, true);
            Button(g, new RectangleF(1179, y, 77, 30), "Zrušit", () => { if (carry != null) CancelCarry(); tool = null; sellTool = false; moveTool = false; }, 0, tool != null || sellTool || moveTool || carry != null);
            TxtWrap(g, CatTips[(int)cat], F(11, false), Pal.Muted, new RectangleF(938, y + 42, 316, 60));
            TxtWrap(g, "Postavené věci přetáhneš myší na jiné místo. R otáčí o 90°, pravé tlačítko ruší, prodej vrací 50 % ceny.", F(10, false), Pal.Dim, new RectangleF(938, y + 100, 316, 40));
        }

        void DrawIcon(Graphics g, ObjType t, RectangleF box)
        {
            float fw = t.W * TS, fh = t.H * TS;
            float s = Math.Min((box.Width - 6) / fw, (box.Height - 6) / fh);
            var st = g.Save();
            g.SetClip(box, CombineMode.Intersect);
            g.TranslateTransform(box.X + (box.Width - fw * s) / 2, box.Y + (box.Height - fh * s) / 2);
            g.ScaleTransform(s, s);
            DrawArt(g, t, 0);
            g.Restore(st);
        }

        static string Seats(int n) { return n + (n == 1 ? " místo" : n < 5 ? " místa" : " míst"); }

        static string StatLine(ObjType t)
        {
            switch (t.Kind)
            {
                case ObjKind.Slot:
                case ObjKind.Table: return "sázka " + FormatKc(t.Bet) + " · " + Seats(t.Seats.Length);
                case ObjKind.Bar: return "drink " + t.Price + " Kč · " + Seats(t.Seats.Length);
                case ObjKind.Wc: return "2 kabinky";
                case ObjKind.Atm: return "poplatek " + t.Price + " Kč za výběr";
                case ObjKind.Sofa: return "odpočinek pro 2 hosty";
                case ObjKind.Bin: return "méně odpadků v okolí";
                default: return "nálada hostů v okolí +" + t.Attract;
            }
        }

        static readonly string[] RoleDesc = {
            "Opravuje porouchané automaty a stoly. Bez technika zůstane stroj rozbitý.",
            "Uklízí odpadky. Nepořádek hostům kazí náladu.",
            "Chytá podvodníky, kteří se snaží obrat automaty."
        };

        void DrawStaffTab(Graphics g)
        {
            float y = 106;
            for (int role = 0; role < 3; role++)
            {
                int rl = role;
                var r = new RectangleF(936, y, 320, 142);
                FillRound(g, B(Pal.Panel2), r, 8);
                var ib = new RectangleF(944, y + 10, 44, 44);
                FillRound(g, B(Color.FromArgb(4, 14, 32)), ib, 6);
                var st = g.Save();
                g.TranslateTransform(ib.X + 22, ib.Y + 26); g.ScaleTransform(2.2f, 2.2f);
                Color body = role == 0 ? Pal.Yellow : role == 1 ? Color.FromArgb(40, 160, 90) : Color.FromArgb(24, 26, 32);
                Color hair = role == 0 ? Pal.Navy : role == 1 ? Color.FromArgb(60, 40, 30) : Color.FromArgb(20, 20, 20);
                Person(g, 0, 0, 0, 1, 0, body, Color.FromArgb(230, 190, 150), hair, false);
                g.Restore(st);
                Txt(g, RoleName[role], F(15, true), Color.White, 998, y + 8);
                int n = StaffCount(role);
                TxtR(g, n + "×", F(18, true), n > 0 ? Pal.Yellow : Pal.Dim, 1248, y + 6);
                Txt(g, FormatKc(RoleWage[role]) + " / den za osobu", F(10.5f, false), Pal.Muted, 998, y + 30);
                TxtWrap(g, RoleDesc[role], F(10.5f, false), Pal.Muted, new RectangleF(944, y + 58, 304, 34));
                string status = role == 0 ? "Porouchané stroje: " + BrokenCount()
                    : role == 1 ? "Odpadky na zemi: " + LitterTotal()
                    : "Chyceno " + cheatsCaught + " · uteklo " + cheatsLost;
                Color sc = role == 0 && BrokenCount() > 0 && n == 0 ? Pal.Red : Pal.Cream;
                Txt(g, status, F(10.5f, true), sc, 944, y + 110);
                Button(g, new RectangleF(1100, y + 104, 72, 28), "Propustit", () => Fire(rl), 0, n > 0);
                Button(g, new RectangleF(1178, y + 104, 72, 28), "Najmout", () => { Hire(rl); Sfx(sPlace); }, 1, n < 30);
                y += 150;
            }
            float wages = 0; foreach (var s in staff) wages += RoleWage[s.Role];
            Txt(g, "Mzdy celkem: " + FormatKc(wages) + " / den", F(12, true), Pal.Text, 938, y + 4);
            Txt(g, "Údržba strojů: " + FormatKc(upkeepSum) + " / den", F(12, true), Pal.Text, 938, y + 24);
        }

        void DrawUpgradesTab(Graphics g)
        {
            float y = 106;
            var r = new RectangleF(936, y, 320, 58);
            FillRound(g, B(Pal.Panel2), r, 8);
            var own = OwnLevels[ownLevel];
            Txt(g, "Rozšíření sálu · " + FloorNames[viewFloor].ToLower(), F(12.5f, true), Color.White, 946, y + 6);
            Txt(g, "Úroveň " + (ownLevel + 1) + " / 4 · " + own.Width + " × " + own.Height + " polí" + (ownLevel < 3 ? " → " + OwnLevels[ownLevel + 1].Width + " × " + OwnLevels[ownLevel + 1].Height : ""), F(10, false), Pal.Muted, 946, y + 27);
            if (ownLevel < 3)
            {
                int cost = OwnCost[ownLevel + 1];
                Button(g, new RectangleF(1140, y + 14, 108, 28), FormatKc(cost), Expand, money >= cost ? 1 : 0, money >= cost);
            }
            else Txt(g, "Maximum", F(11, true), Pal.Green, 1170, y + 20);

            y += 63;
            r = new RectangleF(936, y, 320, 58);
            FillRound(g, B(Pal.Panel2), r, 8);
            int nf = floors.Count;
            Txt(g, "Nové patro", F(12.5f, true), Color.White, 946, y + 6);
            if (nf < 3)
            {
                Txt(g, FloorNames[nf] + " s vlastním sálem a eskalátorem", F(10, false), Pal.Muted, 946, y + 27);
                if (maxStars < FloorStars[nf])
                {
                    DrawStar(g, 1170, y + 29, 7, Pal.Yellow);
                    Txt(g, "od " + FloorStars[nf] + " " + StarWord(FloorStars[nf]), F(11, true), Pal.Cream, 1180, y + 21);
                }
                else Button(g, new RectangleF(1140, y + 14, 108, 28), FormatKc(FloorCost[nf]), BuyFloor, money >= FloorCost[nf] ? 1 : 0, money >= FloorCost[nf]);
            }
            else Txt(g, "Máš všechna tři podlaží.", F(10, false), Pal.Green, 946, y + 27);

            y += 63;
            r = new RectangleF(936, y, 320, 50);
            FillRound(g, B(Pal.Panel2), r, 8);
            Txt(g, "Reklamní kampaň", F(12.5f, true), Color.White, 946, y + 5);
            Txt(g, "+60 % hostů na 24 hodin", F(10, false), Pal.Muted, 946, y + 26);
            if (campaignMin > 0) Txt(g, "běží " + (int)Math.Ceiling(campaignMin / 60) + " h", F(11, true), Pal.Cyan, 1170, y + 16);
            else Button(g, new RectangleF(1140, y + 11, 108, 28), FormatKc(8000), StartCampaign, money >= 8000 ? 1 : 0, money >= 8000);

            y += 55;
            foreach (var u in ups)
            {
                var uu = u;
                r = new RectangleF(936, y, 320, 56);
                bool locked = u.Stars > maxStars;
                FillRound(g, B(Pal.Panel2), r, 8);
                Txt(g, u.Name, F(12.5f, true), locked ? Pal.Dim : Color.White, 946, y + 5);
                TxtWrap(g, u.Desc, F(9.5f, false), locked ? Pal.Dim : Pal.Muted, new RectangleF(946, y + 22, 190, 34));
                if (u.Owned)
                {
                    Check(g, 1170, y + 22, 13, Pal.Green);
                    Txt(g, "Máš", F(12, true), Pal.Green, 1190, y + 20);
                }
                else if (locked)
                {
                    DrawStar(g, 1170, y + 31, 7, Pal.Yellow);
                    Txt(g, "od " + u.Stars + " " + StarWord(u.Stars), F(11, true), Pal.Cream, 1180, y + 23);
                }
                else Button(g, new RectangleF(1142, y + 17, 106, 28), FormatKc(u.Cost), () => BuyUp(uu), money >= u.Cost ? 1 : 0, money >= u.Cost);
                if (r.Contains(mouse)) hoverTip = u.Name + ": " + u.Desc;
                y += 60;
            }
        }

        void FinRow(Graphics g, string name, float v, float y, bool bold, bool sign)
        {
            Txt(g, name, F(11.5f, bold), bold ? Color.White : Pal.Muted, 946, y);
            string s = (sign && v > 0 ? "+" : "") + FormatKc(v);
            TxtR(g, s, F(11.5f, bold), v < 0 ? Pal.Red : bold ? Pal.Green : Pal.Text, 1248, y);
        }

        void DrawFinanceTab(Graphics g)
        {
            float y = 108;
            Txt(g, "Dnes · den " + day, F(13, true), Pal.Yellow, 944, y); y += 24;
            FinRow(g, "Automaty", today.Slots, y, false, true); y += 19;
            FinRow(g, "Stoly", today.Tables, y, false, true); y += 19;
            FinRow(g, "Bar", today.Bar, y, false, true); y += 19;
            FinRow(g, "Bankomaty", today.Atm, y, false, true); y += 19;
            FinRow(g, "Mzdy", -today.Wages, y, false, true); y += 19;
            FinRow(g, "Údržba", -today.Upkeep, y, false, true); y += 19;
            FinRow(g, "Podvodníci a kampaně", -today.Events, y, false, true); y += 21;
            g.DrawLine(P(Pal.Line, 1), 944, y, 1248, y); y += 5;
            FinRow(g, "Provozní zisk", today.Operating, y, true, true); y += 23;
            FinRow(g, "Stavby a vylepšení", -today.Build, y, false, true); y += 19;
            FinRow(g, "Odměny za cíle", today.Rewards, y, false, true); y += 26;
            if (history.Count > 0)
            {
                var last = history[history.Count - 1];
                FinRow(g, "Včera (den " + last.Day + ") provozní zisk", last.Operating, y, false, true);
            }
            y += 30;

            Txt(g, "Provozní zisk za posledních 10 dní", F(11.5f, true), Color.White, 944, y); y += 22;
            var chart = new RectangleF(952, y, 290, 130);
            int n = Math.Min(10, history.Count);
            float max = 1000;
            for (int i = history.Count - n; i < history.Count; i++) max = Math.Max(max, Math.Abs(history[i].Operating));
            float zero = chart.Y + chart.Height * .72f;
            bool anyNeg = false;
            for (int i = history.Count - n; i < history.Count; i++) if (history[i].Operating < 0) anyNeg = true;
            if (!anyNeg) zero = chart.Bottom - 14;
            float up = zero - chart.Y - 12, dn = chart.Bottom - 14 - zero;
            g.DrawLine(P(Pal.Line, 1), chart.X, chart.Y, chart.Right, chart.Y);
            g.DrawLine(P(Pal.Line, 1), chart.X, chart.Y + up / 2 + 12, chart.Right, chart.Y + up / 2 + 12);
            TxtR(g, "max " + FormatKc(max), F(9, false), Pal.Dim, chart.Right, chart.Y - 16);
            if (n == 0) TxtC(g, "Graf se naplní po prvním uzavřeném dni (v 6:00).", F(10.5f, false), Pal.Dim, chart.X + chart.Width / 2, chart.Y + 60);
            float bw = chart.Width / 10f;
            for (int k = 0; k < n; k++)
            {
                var d = history[history.Count - n + k];
                float v = d.Operating;
                float h = v >= 0 ? up * v / max : Math.Max(1, dn) * Math.Min(1, -v / max);
                float x = chart.X + k * bw + 4;
                var bar = v >= 0 ? new RectangleF(x, zero - h, bw - 8, Math.Max(1, h)) : new RectangleF(x, zero, bw - 8, Math.Max(1, h));
                FillRound(g, B(v >= 0 ? Pal.Green : Pal.Red), bar, 2);
                TxtC(g, d.Day.ToString(), F(9, false), Pal.Dim, x + (bw - 8) / 2, chart.Bottom - 5);
            }
            g.DrawLine(P(Pal.Muted, 1), chart.X, zero, chart.Right, zero);
            y = chart.Bottom + 12;
            FinRow(g, "Hodnota kasina", CasinoValue(), y, true, false); y += 21;
            Txt(g, "Hostů celkem: " + totalGuests + " · dnes: " + today.Guests, F(11, false), Pal.Muted, 946, y);
        }

        void DrawGoalsTab(Graphics g)
        {
            float y = 106;
            int st = StarsNow();
            var box = new RectangleF(936, y, 320, 128);
            FillRound(g, B(Pal.Panel2), box, 8);
            if (st >= 5)
            {
                Txt(g, "Máš maximální hodnocení", F(12.5f, true), Pal.Yellow, 946, y + 8);
                for (int i = 0; i < 5; i++) DrawStar(g, 956 + i * 22, y + 44, 9, Pal.Yellow);
            }
            else
            {
                Txt(g, "Co chybí na " + (st + 1) + " " + StarWord(st + 1), F(12.5f, true), Pal.Yellow, 946, y + 7);
                for (int i = 0; i < st + 1; i++) DrawStar(g, 1180 + i * 15, y + 16, 6, i < st ? Pal.Yellow : Pal.Cream);
                float ry = y + 30;
                foreach (var r in StarReqs(st + 1, true))
                {
                    if (r.Value) Check(g, 948, ry + 3, 10, Pal.Green);
                    else g.DrawEllipse(P(Pal.Red, 1.3f), 948, ry + 2, 10, 10);
                    Txt(g, r.Key, F(11, false), r.Value ? Pal.Muted : Pal.Text, 966, ry);
                    ry += 19;
                }
            }
            y += 138;
            Txt(g, "Cíle: od herny ke kasinu snů", F(12.5f, true), Pal.Yellow, 944, y); y += 22;
            for (int i = 0; i < goals.Count; i++)
            {
                var gl = goals[i];
                bool done = i < goalIdx, cur = i == goalIdx;
                if (cur) FillRound(g, B(Color.FromArgb(40, 255, 221, 0)), new RectangleF(938, y - 2, 316, 21), 5);
                if (done) Check(g, 944, y + 3, 10, Pal.Green);
                else g.DrawEllipse(P(cur ? Pal.Yellow : Pal.Dim, 1.3f), 944, y + 3, 10, 10);
                TxtClip(g, gl.Text, F(10.5f, cur), done ? Pal.Dim : cur ? Color.White : Pal.Muted, new RectangleF(960, y, 214, 18));
                TxtR(g, "+" + FormatKc(gl.Reward), F(10, cur), done ? Pal.Dim : Pal.Cream, 1248, y + 1);
                y += 22;
            }
        }

        void DrawGoalCard(Graphics g, RectangleF r)
        {
            FillRound(g, B(Color.FromArgb(24, 40, 20)), r, 8);
            DrawRound(g, P(Color.FromArgb(120, Pal.Yellow), 1), r, 8);
            if (goalIdx >= goals.Count)
            {
                Txt(g, "VŠECHNY CÍLE SPLNĚNY", F(10, true), Pal.Yellow, r.X + 10, r.Y + 8);
                TxtWrap(g, "Kasino je hotové. Hraj dál, zkus 5 hvězd a co nejvyšší hodnotu.", F(11.5f, false), Pal.Text, new RectangleF(r.X + 10, r.Y + 26, r.Width - 20, 50));
                return;
            }
            var gl = goals[goalIdx];
            Txt(g, "CÍL " + (goalIdx + 1) + " / " + goals.Count, F(10, true), Pal.Yellow, r.X + 10, r.Y + 7);
            TxtR(g, "odměna " + FormatKc(gl.Reward), F(10, true), Pal.Cream, r.Right - 10, r.Y + 7);
            TxtWrap(g, gl.Text, F(13, true), Color.White, new RectangleF(r.X + 10, r.Y + 24, r.Width - 20, 36));
            if (gl.Progress != null) Txt(g, gl.Progress(), F(11, false), Pal.Muted, r.X + 10, r.Y + 58);
        }

        // ---------- spodní panel ----------

        void DrawBottomPanel(Graphics g)
        {
            var left = new RectangleF(16, 648, 584, 96);
            var right = new RectangleF(608, 648, 312, 96);
            Card(g, left); Card(g, right);

            Txt(g, "ZPRÁVY", F(9.5f, true), Pal.Yellow, right.X + 12, right.Y + 8);
            int n = Math.Min(4, notes.Count);
            for (int i = 0; i < n; i++)
            {
                var nt = notes[notes.Count - 1 - i];
                float y = right.Y + 24 + i * 17;
                Txt(g, nt.When, F(9, false), Pal.Dim, right.X + 12, y + 1);
                TxtClip(g, nt.T, F(10.5f, i == 0), i == 0 ? nt.C : Mix(nt.C, Pal.Muted, .45f), new RectangleF(right.X + 70, y, right.Width - 80, 16));
            }

            float x = left.X + 14, y0 = left.Y + 10;
            if (sel != null && objs.Contains(sel)) { ObjInfo(g, sel, x, y0); return; }
            if (selGuest != null) { GuestInfo(g, selGuest, x, y0); return; }
            if (selStaff != null) { StaffInfo(g, selStaff, x, y0); return; }
            if (carry != null)
            {
                Txt(g, "Přesouváš: " + carry.T.Name, F(15, true), Pal.Cyan, x, y0);
                TxtWrap(g, "Klikni nebo pusť tlačítko myši tam, kam ho chceš položit. R otočí o 90°. Pravé tlačítko nebo Esc ho vrátí na původní místo. Přesun je zdarma.", F(11.5f, false), Pal.Muted, new RectangleF(x, y0 + 24, 560, 36));
                string ce = InMap(mouse) ? Validate(carry.T, GhostX(), GhostY(), toolDir) : null;
                if (flashErrT > 0 && flashErr != null) ce = flashErr;
                if (ce != null) Txt(g, ce, F(11, true), Pal.Red, x, y0 + 60);
                return;
            }
            if (moveTool)
            {
                Txt(g, "Přesun", F(15, true), Pal.Cyan, x, y0);
                TxtWrap(g, "Klikni na objekt, který chceš přesunout. Hosté od něj odejdou a po položení se zase vrátí.", F(11.5f, false), Pal.Muted, new RectangleF(x, y0 + 26, 560, 40));
                return;
            }
            if (tool != null)
            {
                Txt(g, tool.Name, F(15, true), Color.White, x, y0);
                TxtR(g, FormatKc(CostOf(tool)), F(14, true), Pal.Yellow, left.Right - 14, y0 + 1);
                TxtWrap(g, tool.Desc, F(11.5f, false), Pal.Muted, new RectangleF(x, y0 + 24, 560, 36));
                string err = InMap(mouse) ? CanBuild(tool, GhostX(), GhostY(), toolDir) : null;
                if (flashErrT > 0 && flashErr != null) err = flashErr;
                Txt(g, err != null ? err : "Klikni do sálu a postav. Modré kroužky ukazují, kde budou sedět hosté." + (tool.Rot ? " R otočí o 90°." : ""),
                    F(11, true), err != null ? Pal.Red : Pal.Cream, x, y0 + 60);
                return;
            }
            if (sellTool)
            {
                Txt(g, "Prodej", F(15, true), Pal.Red, x, y0);
                TxtWrap(g, "Klikni na objekt a prodáš ho za polovinu ceny. Pravým tlačítkem nebo Esc režim ukončíš.", F(11.5f, false), Pal.Muted, new RectangleF(x, y0 + 26, 560, 40));
                return;
            }
            if (hoverTip != null)
            {
                TxtWrap(g, hoverTip, F(12, false), Pal.Text, new RectangleF(x, y0 + 2, 560, 70));
                return;
            }
            Txt(g, "Tip", F(13, true), Pal.Yellow, x, y0);
            TxtWrap(g, TipText(), F(11.5f, false), Pal.Muted, new RectangleF(x, y0 + 22, 560, 44));
            Txt(g, "Mezerník pauza · 1–3 rychlost · F5 uložit · F9 načíst · Esc menu · M zvuk", F(10, false), Pal.Dim, x, y0 + 64);
        }

        string TipText()
        {
            if (RatingStars() > PrestigeCap()) return "Hosté jsou spokojení, ale na další hvězdu kasinu chybí vybavení. Co přesně, najdeš v záložce Cíle.";
            if (objs.Count == 0) return "Otevři záložku Stavět, vyber APEX Classic a postav pár automatů vedle sebe. Hosté si k nim sednou z volné strany.";
            if (BrokenCount() > 0 && StaffCount(0) == 0) return "Máš porouchané stroje a žádného technika. Najmi ho v záložce Personál, jinak stroje nevydělávají.";
            if (CountKind(ObjKind.Wc) == 0) return "Hosté brzy budou potřebovat na toaletu. Bez ní odcházejí naštvaní.";
            if (CountKind(ObjKind.Bar) == 0) return "Bar přinese peníze navíc a hosté vydrží hrát déle.";
            if (LitterTotal() > 12 && StaffCount(1) == 0) return "Na zemi je spousta odpadků. Uklízeč a pár košů to vyřeší.";
            if (gameSeats > 0 && guests.Count > gameSeats) return "Hostů je víc než volných míst u her. Postav další automaty.";
            return "Klikni na automat, stůl nebo hosta a uvidíš podrobnosti. Hosté ti řeknou, co se jim nelíbí.";
        }

        void ObjInfo(Graphics g, Obj o, float x, float y)
        {
            Txt(g, o.T.Name, F(15, true), Color.White, x, y);
            float w = TextW(g, o.T.Name, F(15, true)) + 12;
            if (o.T.Breaks)
            {
                string s = o.Broken ? (o.Tech != null ? "Opravuje se" : "Porucha") : "V provozu";
                Color c = o.Broken ? (o.Tech != null ? Pal.Yellow : Pal.Red) : Pal.Green;
                float sw = TextW(g, s, F(10, true)) + 14;
                FillRound(g, B(c), new RectangleF(x + w, y + 2, sw, 18), 9);
                TxtC(g, s, F(10, true), Pal.Ink, x + w + sw / 2, y + 11);
            }
            string l1, l2;
            if (o.T.IsGame)
            {
                l1 = "Hráči " + o.UserCount + " / " + o.Seats.Length + "   ·   sázka " + FormatKc(o.T.Bet) + "   ·   odehráno " + o.Plays + "×";
                l2 = "Zisk dnes " + FormatKc(o.IncomeToday) + "   ·   celkem " + FormatKc(o.IncomeTotal) + "   ·   údržba " + FormatKc(o.T.Upkeep) + "/den";
            }
            else if (o.T.Kind == ObjKind.Decor || o.T.Kind == ObjKind.Bin)
            {
                l1 = o.T.Desc;
                l2 = "Údržba " + FormatKc(o.T.Upkeep) + "/den";
            }
            else
            {
                l1 = "Používá " + o.UserCount + " / " + o.Seats.Length + "   ·   obslouženo " + o.Plays + "×";
                l2 = o.IncomeTotal > 0 ? "Tržba dnes " + FormatKc(o.IncomeToday) + "   ·   celkem " + FormatKc(o.IncomeTotal) : o.T.Desc;
            }
            TxtClip(g, l1, F(11.5f, false), Pal.Text, new RectangleF(x, y + 28, 440, 18));
            TxtClip(g, l2, F(11.5f, false), Pal.Muted, new RectangleF(x, y + 48, 440, 18));
            if (o.Broken && StaffCount(0) == 0) Txt(g, "Bez technika se stroj neopraví.", F(11, true), Pal.Red, x, y + 66);
            var oo = o;
            Button(g, new RectangleF(466, y - 2, 120, 28), "Prodat " + FormatKc(o.T.Cost / 2), () => { Float(oo.X + oo.W / 2f, oo.Y, "+" + FormatKc(oo.T.Cost / 2), Pal.Green); Sell(oo); Sfx(sSell); }, 3, true);
            Button(g, new RectangleF(466, y + 30, 58, 26), "Otočit", () => { if (Rotate(oo)) Sfx(sPlace); }, 0, o.T.Rot);
            Button(g, new RectangleF(528, y + 30, 58, 26), "Přesun", () => PickUp(oo), 0, true);
            Txt(g, "tip: objekt jde i přetáhnout myší", F(9, false), Pal.Dim, 466, y + 62);
        }

        void Bar(Graphics g, string label, float v, float x, float y, bool goodHigh)
        {
            Txt(g, label, F(10, false), Pal.Muted, x, y - 2);
            var r = new RectangleF(x + 70, y + 2, 96, 7);
            FillRound(g, B(Color.FromArgb(4, 14, 32)), r, 3);
            float k = Math.Max(0, Math.Min(1, v / 100));
            float bad = goodHigh ? 1 - k : k;
            Color c = bad > .66f ? Pal.Red : bad > .4f ? Pal.Yellow : Pal.Green;
            FillRound(g, B(c), new RectangleF(r.X, r.Y, Math.Max(3, r.Width * k), r.Height), 3);
        }

        void GuestInfo(Graphics g, Guest gu, float x, float y)
        {
            Txt(g, gu.Name, F(15, true), Color.White, x, y);
            float w = TextW(g, gu.Name, F(15, true)) + 12;
            if (gu.Vip)
            {
                FillRound(g, B(Pal.Gold), new RectangleF(x + w, y + 2, 34, 18), 9);
                TxtC(g, "VIP", F(10, true), Pal.Ink, x + w + 17, y + 11);
            }
            string doing = gu.State == GS.Leave ? "Odchází"
                : gu.State == GS.Use && gu.Target != null ? (gu.Target.T.IsGame ? "Hraje: " + gu.Target.T.Name : "Používá: " + gu.Target.T.Name)
                : gu.Target != null ? "Jde k: " + gu.Target.T.Name : "Rozhlíží se";
            TxtR(g, doing, F(11, true), Pal.Cream, 440, y + 2);
            Txt(g, "Peníze " + FormatKc(gu.Money) + " z " + FormatKc(gu.Budget), F(11, false), Pal.Text, x, y + 26);
            Txt(g, "Výsledek " + (gu.Won >= 0 ? "+" : "") + FormatKc(gu.Won), F(11, false), gu.Won >= 0 ? Pal.Green : Pal.Muted, x, y + 44);
            Bar(g, "Nálada", gu.Happy, 220, y + 28, true);
            Bar(g, "Žízeň", gu.Thirst, 220, y + 46, false);
            Bar(g, "Toaleta", gu.Bladder, 404, y + 28, false);
            Bar(g, "Energie", gu.Energy, 404, y + 46, true);
            if (gu.Thought != "") TxtClip(g, "„" + gu.Thought + "“", F(11.5f, false), Pal.Cream, new RectangleF(x, y + 64, 560, 18));
        }

        void StaffInfo(Graphics g, Staff s, float x, float y)
        {
            Txt(g, s.Name, F(15, true), Color.White, x, y);
            Txt(g, RoleName[s.Role] + " · " + FormatKc(RoleWage[s.Role]) + " / den", F(11, true), Pal.Cream, x, y + 26);
            string doing;
            if (s.Role == 0) doing = s.Job != null ? (s.Mode == 2 ? "Opravuje " : "Jde opravit ") + s.Job.T.Name : "Čeká na poruchu";
            else if (s.Role == 1) doing = s.HasLitter ? (s.Mode == 2 ? "Uklízí" : "Jde uklidit odpadky") : "Obchází sál";
            else doing = "Hlídá herní plochu";
            Txt(g, doing, F(11.5f, false), Pal.Text, x, y + 46);
            Button(g, new RectangleF(466, y - 2, 120, 28), "Propustit", () => { Fire(s.Role); }, 3, true);
        }

        // ---------- překryvy nad mapou ----------

        void DrawOverlaysOnMap(Graphics g)
        {
            if (bannerT > 0 && banner != null)
            {
                float a = Math.Min(1, Math.Min(bannerT / .4f, (4.5f - bannerT) / .25f + .2f));
                var r = new RectangleF(MX + 448 - 290, MY + 14, 580, 66);
                FillRound(g, B((int)(235 * a), Pal.Night), r, 12);
                DrawRound(g, P(Color.FromArgb((int)(255 * a), Pal.Yellow), 2), r, 12);
                TxtC(g, banner, F(20, true), Color.FromArgb((int)(255 * a), Pal.Yellow), r.X + r.Width / 2, r.Y + 22);
                TxtC(g, bannerSub ?? "", F(12, false), Color.FromArgb((int)(255 * a), Pal.Text), r.X + r.Width / 2, r.Y + 47);
            }
            if (reportT > 0 && report != null)
            {
                float a = Math.Min(1, reportT / .5f);
                var r = new RectangleF(MX + 896 - 262, MY + 96, 250, 176);
                FillRound(g, B((int)(240 * a), Pal.Panel), r, 10);
                DrawRound(g, P(Color.FromArgb((int)(255 * a), Pal.Cyan), 1.5f), r, 10);
                Color t = Color.FromArgb((int)(255 * a), Color.White), m = Color.FromArgb((int)(255 * a), Pal.Muted);
                Txt(g, "Den " + report.Day + " – souhrn", F(14, true), Color.FromArgb((int)(255 * a), Pal.Yellow), r.X + 14, r.Y + 10);
                string[] ln = { "Hosté", "Příjmy", "Mzdy a údržba", "Ostatní výdaje" };
                float[] vv = { report.Guests, report.Income, -(report.Wages + report.Upkeep), -report.Events };
                for (int i = 0; i < 4; i++)
                {
                    Txt(g, ln[i], F(11.5f, false), m, r.X + 14, r.Y + 38 + i * 20);
                    TxtR(g, i == 0 ? ((int)vv[i]).ToString() : FormatKc(vv[i]), F(11.5f, true), t, r.Right - 14, r.Y + 38 + i * 20);
                }
                g.DrawLine(P(Color.FromArgb((int)(255 * a), Pal.Line), 1), r.X + 14, r.Y + 122, r.Right - 14, r.Y + 122);
                Txt(g, "Provozní zisk", F(12, true), t, r.X + 14, r.Y + 130);
                TxtR(g, FormatKc(report.Operating), F(15, true), Color.FromArgb((int)(255 * a), report.Operating >= 0 ? Pal.Green : Pal.Red), r.Right - 14, r.Y + 128);
                TxtC(g, "klikni pro zavření", F(9, false), m, r.X + r.Width / 2, r.Bottom - 12);
                btns.Add(new Btn { R = r, A = () => { reportT = 0; } });
            }
            // štítky efektů a přepínač mapy nálady
            float ex = MX + GW * TS - 8;
            foreach (var ef in ActiveEffects())
            {
                var ff = F(10.5f, true);
                float w = TextW(g, ef.Key, ff) + 18;
                ex -= w;
                FillRound(g, B(230, ef.Value), new RectangleF(ex, MY + 8, w, 22), 11);
                TxtC(g, ef.Key, ff, Pal.Ink, ex + w / 2, MY + 19);
                ex -= 6;
            }
            Button(g, new RectangleF(MX + 8, MY + 8, 150, 26), moodMap ? "Mapa nálady: zap (N)" : "Mapa nálady (N)", () => { moodMap = !moodMap; }, moodMap ? 1 : 0, true);
            if (moodMap)
            {
                var lg = new RectangleF(MX + 8, MY + 38, 150, 58);
                FillRound(g, B(225, Pal.Night), lg, 8);
                Color[] lc = { Pal.Green, Pal.Yellow, Pal.Red };
                string[] ln = { "hostům se tu líbí", "bez dekorací", "odpadky, špatná nálada" };
                for (int i = 0; i < 3; i++)
                {
                    g.FillRectangle(B(160, lc[i]), lg.X + 10, lg.Y + 9 + i * 16, 10, 10);
                    Txt(g, ln[i], F(10, false), Pal.Text, lg.X + 26, lg.Y + 6 + i * 16);
                }
            }
            // přepínač pater
            float fx = MX + 8, fy = MY + GH * TS - 34;
            for (int i = 0; i < floors.Count; i++)
            {
                int k = i, n = 0;
                foreach (var gu in guests) if (gu.Floor == i) n++;
                string lbl = FloorNames[i] + "  " + n;
                float w = TextW(g, lbl, F(12, true)) + 26;
                Button(g, new RectangleF(fx, fy, w, 26), lbl, () => SetView(k), viewFloor == i ? 1 : 0, true);
                fx += w + 4;
            }
            if (floors.Count < 3)
                Button(g, new RectangleF(fx, fy, 88, 26), "+ patro", () => { tab = 2; }, 0, true);
            if (screen == Screen.Play && speedIdx == 0 && !bankrupt)
            {
                var r = new RectangleF(MX + 448 - 70, MY + GH * TS - 40, 140, 28);
                FillRound(g, B(220, Pal.Night), r, 14);
                TxtC(g, "PAUZA · mezerník", F(11, true), Pal.Cream, r.X + 70, r.Y + 14);
            }
        }

        // ---------- úvod, menu, nápověda ----------

        void Dim(Graphics g, int a) { g.FillRectangle(B(a, Pal.Night), 0, 0, VW, VH); }

        void DrawTitle(Graphics g)
        {
            Dim(g, 150);
            var r = new RectangleF(VW / 2 - 260, 120, 520, 520);
            FillRound(g, B(240, Pal.Panel), r, 18);
            DrawRound(g, P(Pal.Line, 2), r, 18);
            var f = F(76, true);
            float tw = TextW(g, "APEX", f);
            float lx = VW / 2 - (tw + 94) / 2;
            Txt(g, "APEX", f, Color.White, lx - 6, 146);
            DrawPyramid(g, lx + tw + 50, 164, 86, 70);
            TxtC(g, "KASINO", F(30, true), Pal.Yellow, VW / 2, 268);
            TxtC(g, "Postav vlastní kasino plné automatů APEX.", F(15, false), Pal.Text, VW / 2, 306);
            TxtC(g, "Hosté, jackpoty, personál a pět hvězd hodnocení.", F(13, false), Pal.Muted, VW / 2, 330);

            float by = 368;
            Button(g, new RectangleF(VW / 2 - 150, by, 300, 44), "Nová hra", StartNew, 1, true); by += 54;
            Button(g, new RectangleF(VW / 2 - 150, by, 300, 40), HasSave() ? "Pokračovat v uložené hře" : "Žádná uložená hra", ContinueGame, 0, HasSave()); by += 50;
            Button(g, new RectangleF(VW / 2 - 150, by, 300, 40), "Jak hrát", () => { helpBack = Screen.Title; screen = Screen.Help; }, 0, true); by += 50;
            Button(g, new RectangleF(VW / 2 - 150, by, 300, 40), "Konec", Close, 0, true);
            TxtC(g, "Neoficiální firemní hra · Enter = nová hra", F(10.5f, false), Pal.Dim, VW / 2, 618);
            if (screen == Screen.Help) DrawHelp(g);
        }

        void DrawMenu(Graphics g)
        {
            Dim(g, 170);
            var r = new RectangleF(VW / 2 - 180, 190, 360, 380);
            FillRound(g, B(Pal.Panel), r, 16);
            DrawRound(g, P(Pal.Line, 2), r, 16);
            TxtC(g, "MENU", F(24, true), Pal.Yellow, VW / 2, 226);
            TxtC(g, "Den " + day + " · " + TimeStr() + " · " + FormatKc(money), F(12, false), Pal.Muted, VW / 2, 256);
            float y = 284;
            Button(g, new RectangleF(VW / 2 - 130, y, 260, 40), "Pokračovat", () => { screen = Screen.Play; }, 1, true); y += 50;
            Button(g, new RectangleF(VW / 2 - 130, y, 260, 40), "Uložit hru (F5)", () => { Save(false); screen = Screen.Play; }, 0, true); y += 50;
            Button(g, new RectangleF(VW / 2 - 130, y, 260, 40), "Jak hrát", () => { helpBack = Screen.Menu; screen = Screen.Help; }, 0, true); y += 50;
            Button(g, new RectangleF(VW / 2 - 130, y, 260, 40), "Uložit a do hlavního menu", ToTitle, 0, true); y += 50;
            Button(g, new RectangleF(VW / 2 - 130, y, 260, 40), "Uložit a ukončit", Close, 3, true);
        }

        static readonly string[][] Help = {
            new[] { "Cíl hry", "Z malé herny v Litvínovicích udělej kasino s pěti hvězdami. Cíle vpravo dole tě provedou a za každý dostaneš odměnu." },
            new[] { "Stavění", "Záložka Stavět: vyber objekt a klikni do sálu. Automaty a stoly potřebují volná pole pro hráče – náhled je ukáže modrými kroužky. R otáčí o 90°, postavené věci přetáhneš myší (nebo V), X prodává." },
            new[] { "Patra a vedení", "Od 2 hvězd otevřeš 1. patro, od 4 hvězd 2. patro – přepínáš je dole vlevo na mapě (PageUp/PageDown). V záložce Vedení najmeš manažery; celý tým = režim CEO, kdy se kasino řídí samo." },
            new[] { "Události", "Občas se něco stane – firemní večírek APEX, výpadek proudu, kontrola hygieny. Hra se zastaví a ty rozhodneš, co dál." },
            new[] { "Hosté", "Každý host má peníze, náladu, žízeň, potřebu toalety a energii. Klikni na hosta a uvidíš, co si myslí. Spokojení hosté zvyšují hodnocení, naštvaní ho sráží." },
            new[] { "Peníze", "Automaty a stoly mají výhodu kasina, ale hosté občas vyhrají – i jackpot. Každý den platíš mzdy a údržbu. Den se uzavírá v 6:00 ráno." },
            new[] { "Personál", "Technik opravuje porouchané stroje, uklízeč sbírá odpadky, ochranka chytá podvodníky. Bez nich kasino chátrá." },
            new[] { "Hvězdy", "Hodnocení odemyká lepší stroje: Pyramid a ruletu od 2 hvězd, Jackpot Island od 3, poker od 4. Vylepšení najdeš v záložce Vylepšení." },
            new[] { "Ovládání", "Mezerník pauza · 1, 2, 3 rychlost · R otočit · V přesunout · X / Delete prodat · N mapa nálady · F5 uložit · F9 načíst · M zvuk · Esc menu." },
        };

        void DrawHelp(Graphics g)
        {
            Dim(g, 200);
            var r = new RectangleF(VW / 2 - 330, 70, 660, 620);
            FillRound(g, B(Pal.Panel), r, 16);
            DrawRound(g, P(Pal.Line, 2), r, 16);
            TxtC(g, "JAK HRÁT", F(24, true), Pal.Yellow, VW / 2, 104);
            float y = 134;
            foreach (var h in Help)
            {
                Txt(g, h[0], F(14, true), Color.White, r.X + 30, y);
                TxtWrap(g, h[1], F(12.5f, false), Pal.Muted, new RectangleF(r.X + 150, y + 1, r.Width - 180, 55));
                y += 55;
            }
            Button(g, new RectangleF(VW / 2 - 100, r.Bottom - 58, 200, 40), "Zpět", () => { screen = helpBack; }, 1, true);
        }

        void DrawBankrupt(Graphics g)
        {
            Dim(g, 190);
            var r = new RectangleF(VW / 2 - 220, 220, 440, 300);
            FillRound(g, B(Pal.Panel), r, 16);
            DrawRound(g, P(Pal.Red, 2), r, 16);
            TxtC(g, "BANKROT", F(30, true), Pal.Red, VW / 2, 264);
            TxtC(g, "Dluhy přerostly přes 30 000 Kč a banka kasino zavřela.", F(13, false), Pal.Text, VW / 2, 304);
            TxtC(g, "Kasino vydrželo " + day + " dní · hostů celkem " + totalGuests, F(12, false), Pal.Muted, VW / 2, 330);
            Button(g, new RectangleF(VW / 2 - 150, 372, 300, 42), "Nová hra", StartNew, 1, true);
            Button(g, new RectangleF(VW / 2 - 150, 424, 300, 40), "Do hlavního menu", () => { bankrupt = false; ToTitle(); }, 0, true);
        }
    }
}
