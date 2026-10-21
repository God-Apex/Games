'use strict';
// Boot: DOM wiring and the first connection.
/* ---------------- wiring ---------------- */
document.querySelectorAll('[data-ic]').forEach(el => { el.outerHTML = SVG[el.dataset.ic]; });
function staticIcons() { document.querySelectorAll('img[data-icon]').forEach(img => { img.src = iconImg(img.dataset.icon, img.dataset.col || PAL.gilt); }); }
staticIcons();
$('#name').value = load('hmk_name', '');
let nameTimer = 0;
$('#name').addEventListener('input', () => {
  clearTimeout(nameTimer);
  nameTimer = setTimeout(() => { save('hmk_name', $('#name').value); send({ t: 'hello', name: $('#name').value }); }, 300);
});
S.tips = load('hmk_tips', '1') === '1';
$('#tipsChk').checked = S.tips;
$('#tipsChk').addEventListener('change', () => { S.tips = $('#tipsChk').checked; save('hmk_tips', S.tips ? '1' : '0'); });
// the lobby buttons (ready, start, solo, kick, help, tutorial) are wired in lobby.js
$('#helpClose').onclick = () => toggleHelp(false);
$('#helpOv').addEventListener('click', ev => { if (ev.target.id === 'helpOv') toggleHelp(false); });
// during play a clicked button never keeps focus, so Enter or Space cannot fire it again (the lobby keeps focus for keyboard users)
document.addEventListener('click', ev => { const b = S.inGame && ev.target.closest && ev.target.closest('button'); if (b) b.blur(); });
// the board canvas follows its box (the top bar can wrap without a window resize)
if (window.ResizeObserver) new ResizeObserver(() => { if (S.inGame) resize(); }).observe($('#board'));
applyOpt();
uiCrown($('#logoCrown'), 'win');
drawLobbyBg();
if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => {
  if (typeof SPR !== 'undefined') SPR.clear();
  if (typeof ICON_URL !== 'undefined') { ICON_URL.clear(); staticIcons(); if (S.defs) { renderDeck(); renderSettings(true); } }
  if (typeof BOARD_KEY !== 'undefined') BOARD_KEY = '';
});
connect();
