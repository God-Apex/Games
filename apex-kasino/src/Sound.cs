using System;
using System.IO;
using System.Media;
using System.Text;

namespace ApexKasino
{
    // krátké zvuky syntetizované do WAV v paměti
    partial class GameForm
    {
        bool muted;
        SoundPlayer sClick, sPlace, sSell, sErr, sWin, sJack, sGoal, sDay, sBreak, sLose;

        void InitSounds()
        {
            sClick = Snd(new[] { 1400 }, 22, .12, false);
            sPlace = Snd(new[] { 523, 784 }, 55, .2, true);
            sSell = Snd(new[] { 660, 440 }, 60, .18, true);
            sErr = Snd(new[] { 185, 150 }, 90, .2, true);
            sWin = Snd(new[] { 784, 988, 1175 }, 55, .16, true);
            sJack = Snd(new[] { 523, 659, 784, 1047, 784, 1047, 1319, 1568 }, 80, .17, true);
            sGoal = Snd(new[] { 659, 784, 1047, 1319 }, 95, .17, true);
            sDay = Snd(new[] { 988, 784, 659, 784, 988 }, 90, .15, false);
            sBreak = Snd(new[] { 247, 196 }, 110, .18, true);
            sLose = Snd(new[] { 392, 330, 262, 196, 131 }, 150, .2, true);
        }

        void Sfx(SoundPlayer p)
        {
            if (muted || p == null || screen == Screen.Title && p != sClick) return;
            try { p.Play(); } catch { }
        }

        static SoundPlayer Snd(int[] freqs, int ms, double vol, bool square)
        {
            const int rate = 22050;
            int per = rate * ms / 1000, n = per * freqs.Length;
            var mem = new MemoryStream();
            var w = new BinaryWriter(mem);
            w.Write(Encoding.ASCII.GetBytes("RIFF")); w.Write(36 + n * 2);
            w.Write(Encoding.ASCII.GetBytes("WAVE")); w.Write(Encoding.ASCII.GetBytes("fmt "));
            w.Write(16); w.Write((short)1); w.Write((short)1); w.Write(rate); w.Write(rate * 2);
            w.Write((short)2); w.Write((short)16);
            w.Write(Encoding.ASCII.GetBytes("data")); w.Write(n * 2);
            foreach (int f in freqs)
                for (int j = 0; j < per; j++)
                {
                    double env = Math.Min(1, j / 120.0) * (1 - j / (double)per);
                    double ph = Math.Sin(2 * Math.PI * f * j / rate);
                    double v = square ? Math.Sign(ph) * .45 + ph * .2 : ph;
                    w.Write((short)(v * env * vol * 32767));
                }
            w.Flush();
            mem.Position = 0;
            var sp = new SoundPlayer(mem);
            try { sp.Load(); } catch { }
            return sp;
        }
    }
}
