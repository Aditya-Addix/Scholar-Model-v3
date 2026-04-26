// --- PREMIUM THEME ENGINE ---
(function initTheme() {
const savedTheme = localStorage.getItem('addix_theme');
if (savedTheme === 'light') { document.body.classList.add('light-theme'); }
})();

document.addEventListener('DOMContentLoaded', () => {
const themeBtn = document.getElementById('theme-toggle');
if (themeBtn) {
themeBtn.addEventListener('click', () => {
document.body.classList.toggle('light-theme');
const isLight = document.body.classList.contains('light-theme');
localStorage.setItem('addix_theme', isLight ? 'light' : 'dark');
});
}
});
