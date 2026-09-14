#!/usr/bin/env python3
"""
Interface web locale pour converser avec Qwen (profil `brain`, LM Studio sur le Mac) depuis le PC.

    C:\\Python311\\python.exe qwen_web.py            # puis ouvrir http://localhost:8765
    C:\\Python311\\python.exe qwen_web.py --port 9000
    C:\\Python311\\python.exe qwen_web.py --reseau        # aussi pour les autres appareils de la maison

Conversation multi-tours, façon Claude Code : le fil complet est renvoyé au modèle à chaque tour,
la réflexion s'affiche repliée sous chaque réponse, la réponse s'écrit au fur et à mesure en Markdown.
Réglages par conversation : réflexion on/off (bloc <think> vide pré-rempli), budget de tokens, température.

Audio : un bouton micro (ou un fichier audio déposé) est transcrit sur le PC par Whisper, en réutilisant
l'outil D:\\AudioToTxt\\stt\\transcrire.py (faster-whisper, GPU puis CPU). Le modèle Whisper est chargé
au premier usage puis reste en mémoire. Lancer avec le Python qui a faster-whisper (C:\\Python311).

Le bouton « Charger brain » ouvre un SSH avec le mot de passe (une fois) via resumer.py si le modèle
n'est pas résident. Journal : un .md par échange dans ./journal, jamais effacé par le script.
"""
import argparse
import datetime as dt
import html
import json
import os
import sys
import tempfile
import threading
import urllib.error
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import resumer  # noqa: E402  — MAC_IP, PORT, IDENTIFIANT, ssh_ouvrir, preparer_mac

BASE = f"http://{resumer.MAC_IP}:{resumer.PORT}"
JOURNAL = Path(__file__).resolve().parent / "journal"   # un .md par échange, jamais effacé par le script

# Transcription : l'outil speech-to-text existant, importé tel quel depuis son dossier.
STT_DOSSIER = Path(r"D:\AudioToTxt\stt")
WHISPER_MODELES = [Path(r"D:\AudioToTxt\python\whisper-medium"), Path(r"C:\IA_Locale\python\whisper-medium")]
WHISPER_LANGUE = "fr"
EXTENSIONS_AUDIO = {".opus", ".ogg", ".mp3", ".m4a", ".wav", ".aac", ".flac", ".mp4", ".webm", ".mpeg", ".mpga"}

MAX_TOKENS_MIN, MAX_TOKENS_MAX = 256, 32768
TEMPERATURE_MAX = 2.0
PREFILL_SANS_REFLEXION = "<think>\n\n</think>\n\n"   # tour assistant amorcé : Qwen3 répond alors sans réfléchir

# ---------------------------------------------------------------------------------------------------
# Rendu Markdown (JavaScript exécuté dans la page ; isolé ici pour être testé avec node).
# Volontairement sans bibliothèque : titres, gras, italique, code, listes, liens, tableaux, citations.
# Tout le texte est échappé avant mise en forme : rien de ce que renvoie le modèle n'est interprété en HTML.
SCRIPT_MD = r"""
function esc(s) { return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;'); }
function enLigne(s) {
  s = esc(s);
  s = s.replace(/`([^`]+)`/g, (_, c) => '<code>' + c + '</code>');
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/(^|[^*\w])\*([^*\n]+)\*(?!\w)/g, '$1<em>$2</em>');
  s = s.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, t, u) => /^(https?:|mailto:|\/|#)/i.test(u) ? '<a href="' + u + '" target="_blank" rel="noopener">' + t + '</a>' : t);
  return s;
}
function md(src) {
  const lignes = src.replace(/\r\n?/g, '\n').split('\n');
  const out = [];
  let i = 0;
  const para = [];
  const videPara = () => { if (para.length) { out.push('<p>' + para.map(enLigne).join('<br>') + '</p>'); para.length = 0; } };
  while (i < lignes.length) {
    const l = lignes[i];
    let m;
    if ((m = l.match(/^```\s*(\w*)/))) {
      videPara();
      const code = []; i++;
      while (i < lignes.length && !/^```/.test(lignes[i])) code.push(lignes[i++]);
      i++;
      out.push('<pre><code' + (m[1] ? ' class="lang-' + m[1] + '"' : '') + '>' + esc(code.join('\n')) + '\n</code></pre>');
      continue;
    }
    if ((m = l.match(/^(#{1,6})\s+(.*)$/))) { videPara(); out.push('<h' + m[1].length + '>' + enLigne(m[2]) + '</h' + m[1].length + '>'); i++; continue; }
    if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(l)) { videPara(); out.push('<hr>'); i++; continue; }
    if (/^\s*[-*+]\s+/.test(l)) {
      videPara(); const items = [];
      while (i < lignes.length && /^\s*[-*+]\s+/.test(lignes[i])) items.push('<li>' + enLigne(lignes[i++].replace(/^\s*[-*+]\s+/, '')) + '</li>');
      out.push('<ul>' + items.join('') + '</ul>'); continue;
    }
    if (/^\s*\d+[.)]\s+/.test(l)) {
      videPara(); const items = [];
      while (i < lignes.length && /^\s*\d+[.)]\s+/.test(lignes[i])) items.push('<li>' + enLigne(lignes[i++].replace(/^\s*\d+[.)]\s+/, '')) + '</li>');
      out.push('<ol>' + items.join('') + '</ol>'); continue;
    }
    if (/^>\s?/.test(l)) {
      videPara(); const q = [];
      while (i < lignes.length && /^>\s?/.test(lignes[i])) q.push(lignes[i++].replace(/^>\s?/, ''));
      out.push('<blockquote>' + md(q.join('\n')) + '</blockquote>'); continue;
    }
    if (/^\s*\|.*\|\s*$/.test(l) && i + 1 < lignes.length && /^\s*\|?\s*:?-{2,}/.test(lignes[i + 1])) {
      videPara();
      const cellules = s => s.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(c => c.trim());
      const tete = cellules(l); i += 2; const corps = [];
      while (i < lignes.length && /^\s*\|.*\|\s*$/.test(lignes[i])) corps.push('<tr>' + cellules(lignes[i++]).map(c => '<td>' + enLigne(c) + '</td>').join('') + '</tr>');
      out.push('<table><thead><tr>' + tete.map(c => '<th>' + enLigne(c) + '</th>').join('') + '</tr></thead><tbody>' + corps.join('') + '</tbody></table>');
      continue;
    }
    if (!l.trim()) { videPara(); i++; continue; }
    para.push(l); i++;
  }
  videPara();
  return out.join('\n');
}
"""

PAGE = r"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>Qwen · brain</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root { color-scheme: light dark;
    --bord:#d0d4da; --fond:#f6f7f9; --carte:#fff; --texte:#1c1e21; --muted:#6b7280; --accent:#1d4ed8; --accent-fond:#eff6ff;
    --user:#e8eefc; --ok:#15803d; --ko:#b91c1c; --code:#f1f3f5; }
  @media (prefers-color-scheme: dark) { :root {
    --bord:#3a3f47; --fond:#1b1d21; --carte:#24272d; --texte:#e6e8eb; --muted:#9aa3ad; --accent:#7aa2ff; --accent-fond:#1f2a44;
    --user:#2b3550; --ok:#4ade80; --ko:#f87171; --code:#1b1d21; } }
  * { box-sizing:border-box }
  html, body { height:100% }
  body { margin:0; font:14px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif; color:var(--texte); background:var(--fond); display:flex; flex-direction:column }
  header { display:flex; gap:12px; align-items:center; flex-wrap:wrap; padding:10px 16px; border-bottom:1px solid var(--bord); background:var(--carte); position:sticky; top:0; z-index:2 }
  header h1 { font-size:15px; margin:0 12px 0 0 }
  header a { color:var(--accent); text-decoration:none; font-size:13px }
  .etat { color:var(--muted); font-size:13px; display:flex; gap:14px; align-items:center; flex-wrap:wrap }
  .pastille { display:inline-block; width:9px; height:9px; border-radius:50%; background:#9ca3af; margin-right:6px; vertical-align:middle }
  .pastille.ok { background:var(--ok) } .pastille.ko { background:var(--ko) } .pastille.encours { background:#f59e0b }
  .espace { flex:1 }
  button { font:inherit; padding:6px 12px; border-radius:6px; border:1px solid var(--bord); background:var(--carte); color:var(--texte); cursor:pointer }
  button.prim { background:var(--accent); color:#fff; border-color:var(--accent) }
  button.petit { padding:2px 8px; font-size:12px; color:var(--muted) }
  button:disabled { opacity:.5; cursor:default }
  button.actif { background:var(--ko); color:#fff; border-color:var(--ko) }
  #fil { flex:1; overflow-y:auto; padding:18px 16px 8px }
  #fil > div { max-width: 900px; margin:0 auto }
  .msg { margin:0 0 18px; display:flex; flex-direction:column }
  .msg.user .bulle { background:var(--user); border-radius:12px 12px 2px 12px; padding:10px 14px; align-self:flex-end; max-width:85%; white-space:pre-wrap }
  .msg.assistant .bulle { padding:2px 0 }
  .msg .qui { font-size:12px; color:var(--muted); margin:0 4px 4px; }
  .msg.user .qui { align-self:flex-end }
  .msg .actions { display:flex; gap:6px; margin:6px 0 0; opacity:0; transition:opacity .15s }
  .msg:hover .actions { opacity:1 }
  .piece { display:inline-block; font-size:12px; border:1px solid var(--bord); border-radius:999px; padding:1px 8px; margin:4px 4px 0 0; color:var(--muted); background:var(--carte) }
  details.reflexion { margin:4px 0 8px; border-left:3px solid var(--bord); padding-left:10px }
  details.reflexion summary { cursor:pointer; color:var(--muted); font-size:13px; list-style:none }
  details.reflexion summary::before { content:'▸ '; } details.reflexion[open] summary::before { content:'▾ '; }
  .pensee { white-space:pre-wrap; color:var(--muted); font-size:13px; max-height:280px; overflow:auto; margin-top:4px }
  .rendu { overflow-wrap:anywhere }
  .rendu p { margin:0 0 10px } .rendu ul, .rendu ol { margin:0 0 10px; padding-left:22px } .rendu li { margin:2px 0 }
  .rendu h1, .rendu h2, .rendu h3, .rendu h4 { margin:14px 0 6px; line-height:1.3 } .rendu h1{font-size:19px} .rendu h2{font-size:17px} .rendu h3{font-size:15px}
  .rendu code { font-family:ui-monospace, Consolas, monospace; font-size:12.5px; background:var(--code); padding:1px 5px; border-radius:4px }
  .rendu pre { background:var(--code); border:1px solid var(--bord); border-radius:8px; padding:10px 12px; overflow:auto; position:relative; margin:0 0 10px }
  .rendu pre code { background:none; padding:0 } .rendu pre .copier-code { position:absolute; top:6px; right:6px; opacity:0 } .rendu pre:hover .copier-code { opacity:1 }
  .rendu blockquote { margin:0 0 10px; padding:2px 12px; border-left:3px solid var(--bord); color:var(--muted) }
  .rendu table { border-collapse:collapse; margin:0 0 10px; display:block; overflow-x:auto } .rendu th, .rendu td { border:1px solid var(--bord); padding:4px 8px; text-align:left }
  .rendu hr { border:0; border-top:1px solid var(--bord); margin:12px 0 }
  .curseur::after { content:'▍'; color:var(--accent); animation:cl 1s steps(2) infinite } @keyframes cl { to { opacity:0 } }
  .info { color:var(--muted); font-size:12px; margin-top:4px }
  .erreur { color:var(--ko); white-space:pre-wrap; margin:4px 0 12px }
  #bas { border-top:1px solid var(--bord); background:var(--carte); padding:10px 16px 12px }
  #bas > div { max-width:900px; margin:0 auto }
  details.panneau { margin-bottom:8px } details.panneau summary { cursor:pointer; color:var(--muted); font-size:13px }
  .reglages { display:flex; gap:18px; flex-wrap:wrap; align-items:center; padding:8px 0 4px; font-size:13px }
  .reglages label { display:flex; gap:8px; align-items:center } .reglages input[type=range] { width:130px } .reglages output { min-width:44px; font-variant-numeric:tabular-nums }
  #systeme { width:100%; min-height:54px; border:1px solid var(--bord); border-radius:6px; padding:8px; font:inherit; resize:vertical; background:var(--fond); color:var(--texte); margin-top:6px }
  #composeur { border:1px solid var(--bord); border-radius:10px; background:var(--fond); padding:8px 8px 6px }
  #composeur.sur { border-color:var(--accent); background:var(--accent-fond) }
  #message { width:100%; border:0; background:transparent; color:var(--texte); font:inherit; resize:none; min-height:44px; max-height:260px; outline:none; padding:4px }
  .barre { display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-top:4px }
  #chrono { color:var(--muted); font-variant-numeric:tabular-nums; font-size:13px }
  #pieces { display:flex; flex-wrap:wrap }
  .aide { color:var(--muted); font-size:12px; margin-top:6px }
  dialog { border:1px solid var(--bord); border-radius:8px; padding:20px; max-width:420px; background:var(--carte); color:var(--texte) }
  dialog input { width:100%; padding:8px; font:inherit; border:1px solid var(--bord); border-radius:6px; margin:8px 0 12px; background:var(--fond); color:var(--texte) }
  #journal { font-family:ui-monospace, monospace; font-size:12px; white-space:pre-wrap; color:var(--muted); max-height:200px; overflow:auto }
  .vide { color:var(--muted); text-align:center; margin-top:60px }
  input[type=file] { display:none }
</style></head><body>
<header>
  <h1>Qwen · brain</h1>
  <span class="etat">
    <span><span class="pastille" id="p-brain"></span><span id="etat-brain">vérification…</span></span>
    <button id="btn-charger" class="petit" hidden>Charger brain</button>
    <span><span class="pastille" id="p-whisper"></span><span id="etat-whisper">Whisper</span></span>
  </span>
  <span class="espace"></span>
  <a href="/journal">journal</a>
  <button id="btn-exporter" class="petit">Exporter .md</button>
  <button id="btn-nouveau" class="petit">Nouvelle conversation</button>
</header>

<div id="fil"><div id="fil-int"><div class="vide" id="vide">Pose une question, dicte-la au micro, ou dépose un fichier texte ou audio.</div></div></div>

<div id="bas"><div>
  <details class="panneau" id="pan-systeme"><summary>Instruction système <span id="systeme-resume"></span></summary>
    <textarea id="systeme" placeholder="Optionnel. Envoyée une fois, en tête de la conversation (ex. : « Réponds en français, de façon concise. »)."></textarea>
  </details>
  <details class="panneau" id="pan-reglages"><summary>Réglages : <span id="reglages-resume"></span></summary>
    <div class="reglages">
      <label><input type="checkbox" id="reflexion" checked> réflexion</label>
      <label>budget <input type="range" id="max_tokens" min="256" max="32768" step="256"><output id="o-max_tokens"></output></label>
      <label>température <input type="range" id="temperature" min="0" max="1.2" step="0.05"><output id="o-temperature"></output></label>
    </div>
  </details>
  <div id="composeur">
    <div id="pieces"></div>
    <textarea id="message" placeholder="Écris ton message… (Entrée pour envoyer, Maj+Entrée pour une nouvelle ligne)"></textarea>
    <div class="barre">
      <button id="btn-micro" title="Dicter (Whisper local)">🎤 Dicter</button>
      <button id="btn-fichier" title="Joindre un fichier texte ou audio">📎 Fichier</button>
      <input type="file" id="fichier" accept=".txt,.md,.log,.csv,.json,text/*,.opus,.ogg,.mp3,.m4a,.wav,.aac,.flac,.mp4,.webm,audio/*">
      <span id="chrono"></span>
      <span class="espace"></span>
      <button id="btn-stop" disabled>Arrêter</button>
      <button class="prim" id="btn-envoyer">Envoyer</button>
    </div>
  </div>
  <div class="aide" id="aide"></div>
</div></div>

<dialog id="dlg">
  <form method="dialog">
    <div>Mot de passe SSH de <b id="dlg-compte"></b> pour charger le modèle (une à deux minutes) :</div>
    <input type="password" id="mdp" autocomplete="current-password">
    <div id="journal"></div>
    <div class="barre"><button class="prim" id="btn-dlg-ok" type="button">Charger</button><button type="submit">Fermer</button></div>
  </form>
</dialog>

<script>
__SCRIPT_MD__
const $ = id => document.getElementById(id);
const CLE = 'qwen_web.reglages';
let messages = [];          // fil envoyé au modèle : {role, content}
let pieces = [];            // pièces jointes en attente : {nom, contenu}
let ctrl = null, chronoId = null, enregistreur = null;

// ---- réglages (mémorisés dans le navigateur) -------------------------------------------------
function lireReglages() {
  return { reflexion: $('reflexion').checked, max_tokens: +$('max_tokens').value, temperature: +$('temperature').value, systeme: $('systeme').value };
}
function afficherReglages() {
  const r = lireReglages();
  $('o-max_tokens').textContent = r.max_tokens.toLocaleString('fr');
  $('o-temperature').textContent = r.temperature.toFixed(2);
  $('reglages-resume').textContent = (r.reflexion ? 'réflexion' : 'sans réflexion') + ' · ' + r.max_tokens.toLocaleString('fr') + ' tokens · T ' + r.temperature.toFixed(2);
  $('systeme-resume').textContent = r.systeme.trim() ? '— ' + r.systeme.trim().slice(0, 60) : '(vide)';
  try { localStorage.setItem(CLE, JSON.stringify(r)); } catch {}
}
(function initReglages() {
  let r = { reflexion: true, max_tokens: __MAX_TOKENS__, temperature: 0.3, systeme: '' };
  try { r = Object.assign(r, JSON.parse(localStorage.getItem(CLE) || '{}')); } catch {}
  $('reflexion').checked = r.reflexion; $('max_tokens').value = r.max_tokens; $('temperature').value = r.temperature; $('systeme').value = r.systeme;
  for (const id of ['reflexion', 'max_tokens', 'temperature', 'systeme']) $(id).addEventListener('input', afficherReglages);
  afficherReglages();
})();

// ---- état des modèles -----------------------------------------------------------------------
async function etat() {
  try {
    const r = await (await fetch('/api/etat')).json();
    $('dlg-compte').textContent = r.compte;
    if (!r.serveur) { $('p-brain').className = 'pastille ko'; $('etat-brain').textContent = 'LM Studio injoignable sur ' + r.base; $('btn-charger').hidden = false; }
    else if (r.brain) { $('p-brain').className = 'pastille ok'; $('etat-brain').textContent = 'brain résident sur ' + r.base; $('btn-charger').hidden = true; }
    else { $('p-brain').className = 'pastille ko'; $('etat-brain').textContent = 'serveur joignable, brain non chargé'; $('btn-charger').hidden = false; }
    $('p-whisper').className = 'pastille ' + (r.whisper === 'charge' ? 'ok' : r.whisper === 'chargement' ? 'encours' : r.whisper === 'absent' ? 'ko' : '');
    $('etat-whisper').textContent = { charge: 'Whisper prêt', chargement: 'Whisper en chargement…', absent: 'Whisper indisponible : ' + (r.whisper_erreur || ''), pret: 'Whisper (chargé au premier usage)' }[r.whisper] || 'Whisper';
    $('btn-micro').disabled = r.whisper === 'absent';
    return r;
  } catch (e) { $('p-brain').className = 'pastille ko'; $('etat-brain').textContent = 'relais local injoignable'; }
}
$('btn-charger').onclick = () => { $('journal').textContent = ''; $('dlg').showModal(); $('mdp').focus(); };
$('btn-dlg-ok').onclick = async () => {
  $('btn-dlg-ok').disabled = true; $('journal').textContent = 'connexion SSH…\n';
  try {
    const r = await fetch('/api/charger', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ mdp: $('mdp').value }) });
    const j = await r.json();
    $('journal').textContent += j.journal || '';
    if (j.ok) { $('journal').textContent += '\nchargé.'; await etat(); } else { $('journal').textContent += '\nÉCHEC : ' + (j.erreur || ''); }
  } catch (e) { $('journal').textContent += '\nerreur : ' + e; }
  $('btn-dlg-ok').disabled = false; $('mdp').value = '';
};

// ---- fil de conversation --------------------------------------------------------------------
function defiler() { $('fil').scrollTop = $('fil').scrollHeight; }
function copier(texte) {
  if (navigator.clipboard) return navigator.clipboard.writeText(texte);
  // Sans contexte sécurisé (page ouverte en http:// depuis un autre appareil), seul l'ancien mécanisme reste.
  const t = document.createElement('textarea'); t.value = texte; t.style.position = 'fixed'; t.style.opacity = '0';
  document.body.appendChild(t); t.select(); try { document.execCommand('copy'); } catch {} t.remove();
}
function ajouterMessage(role, texte, piecesJointes) {
  $('vide').hidden = true;
  const m = document.createElement('div'); m.className = 'msg ' + role;
  const qui = document.createElement('div'); qui.className = 'qui'; qui.textContent = role === 'user' ? 'Toi' : 'Qwen'; m.appendChild(qui);
  if (role === 'user') {
    const b = document.createElement('div'); b.className = 'bulle'; b.textContent = texte;
    if (piecesJointes && piecesJointes.length) { const p = document.createElement('div'); for (const pj of piecesJointes) { const s = document.createElement('span'); s.className = 'piece'; s.textContent = '📎 ' + pj; p.appendChild(s); } b.appendChild(p); }
    m.appendChild(b);
  } else {
    const det = document.createElement('details'); det.className = 'reflexion'; det.hidden = true; det.open = true;
    det.innerHTML = '<summary>Réflexion</summary><div class="pensee"></div>'; m.appendChild(det);
    const b = document.createElement('div'); b.className = 'bulle rendu curseur'; m.appendChild(b);
    const info = document.createElement('div'); info.className = 'info'; m.appendChild(info);
  }
  const act = document.createElement('div'); act.className = 'actions';
  const cp = document.createElement('button'); cp.className = 'petit'; cp.textContent = 'Copier';
  cp.onclick = () => { copier(m.dataset.brut || texte); cp.textContent = 'Copié'; setTimeout(() => cp.textContent = 'Copier', 1200); };
  act.appendChild(cp); m.appendChild(act);
  $('fil-int').appendChild(m); defiler();
  return m;
}
function rendre(el, texte) {
  el.innerHTML = md(texte);
  for (const pre of el.querySelectorAll('pre')) {
    const b = document.createElement('button'); b.className = 'petit copier-code'; b.textContent = 'copier';
    b.onclick = () => { copier(pre.querySelector('code').textContent.replace(/\n$/, '')); b.textContent = 'copié'; setTimeout(() => b.textContent = 'copier', 1200); };
    pre.appendChild(b);
  }
}
function chrono(on, cible) {
  clearInterval(chronoId);
  if (!on) return;
  const t0 = Date.now();
  chronoId = setInterval(() => { const s = Math.round((Date.now() - t0) / 1000); cible.textContent = Math.floor(s / 60) + ' min ' + String(s % 60).padStart(2, '0') + ' s'; }, 1000);
}

async function envoyer() {
  if (ctrl) return;
  let texte = $('message').value.trim();
  if (!texte && !pieces.length) return;
  const nomsPieces = pieces.map(p => p.nom);
  let contenu = texte;
  for (const p of pieces) contenu += (contenu ? '\n\n' : '') + '--- ' + p.nom + ' ---\n' + p.contenu;
  messages.push({ role: 'user', content: contenu });
  ajouterMessage('user', texte || '(fichier seul)', nomsPieces);
  $('message').value = ''; pieces = []; afficherPieces(); ajusterHauteur();
  const m = ajouterMessage('assistant', '');
  const pensee = m.querySelector('.pensee'), det = m.querySelector('details'), bulle = m.querySelector('.bulle'), info = m.querySelector('.info');
  const r = lireReglages();
  $('btn-envoyer').disabled = true; $('btn-stop').disabled = false; chrono(true, $('chrono'));
  ctrl = new AbortController();
  let dansThink = false, tampon = '', brut = '', refl = '', dernierRendu = 0;
  const rafraichir = force => { const t = Date.now(); if (force || t - dernierRendu > 120) { rendre(bulle, brut); dernierRendu = t; defiler(); } };
  try {
    const rep = await fetch('/api/chat', { method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ messages, systeme: r.systeme, reflexion: r.reflexion, max_tokens: r.max_tokens, temperature: r.temperature }), signal: ctrl.signal });
    if (!rep.ok) throw new Error(await rep.text());
    const lecteur = rep.body.getReader(), dec = new TextDecoder();
    for (;;) {
      const { value, done } = await lecteur.read();
      if (done) break;
      tampon += dec.decode(value, { stream: true });
      const lignes = tampon.split('\n'); tampon = lignes.pop();
      for (const l of lignes) {
        if (!l.startsWith('data: ')) continue;
        const d = l.slice(6);
        if (d === '[DONE]') continue;
        let ev; try { ev = JSON.parse(d); } catch { continue; }
        if (ev.erreur) throw new Error(ev.erreur);
        if (ev.journal) { info.textContent += ' · journal : ' + ev.journal; continue; }
        const delta = ((ev.choices || [])[0] || {}).delta || {};
        if (delta.reasoning_content) { refl += delta.reasoning_content; }
        // Repli : certains builds mettent la réflexion dans content entre <think>…</think>.
        let c = delta.content || '';
        while (c) {
          if (dansThink) { const i = c.indexOf('</think>'); if (i < 0) { refl += c; c = ''; } else { refl += c.slice(0, i); c = c.slice(i + 8); dansThink = false; } }
          else { const i = c.indexOf('<think>'); if (i < 0) { brut += c; c = ''; } else { brut += c.slice(0, i); c = c.slice(i + 7); dansThink = true; } }
        }
        if (refl) { det.hidden = false; pensee.textContent = refl; pensee.scrollTop = pensee.scrollHeight; }
        if (brut && det.open) det.open = false;
        rafraichir(false);
      }
    }
    brut = brut.trim();
    if (!brut) throw new Error('Réponse vide : la réflexion a consommé tout le budget (max_tokens). Augmente le budget ou coupe la réflexion.');
    messages.push({ role: 'assistant', content: brut });
  } catch (e) {
    if (e.name === 'AbortError') { brut = brut.trim(); if (brut) messages.push({ role: 'assistant', content: brut + '\n\n*(arrêté)*' }); else messages.pop(); info.textContent = 'arrêté' + info.textContent; }
    else { messages.pop(); const err = document.createElement('div'); err.className = 'erreur'; err.textContent = 'Erreur : ' + e.message; m.appendChild(err); }
  }
  rendre(bulle, brut); bulle.classList.remove('curseur'); m.dataset.brut = brut;
  info.textContent = $('chrono').textContent + (r.reflexion ? '' : ' · sans réflexion') + info.textContent;
  $('btn-envoyer').disabled = false; $('btn-stop').disabled = true; chrono(false); $('chrono').textContent = ''; ctrl = null; defiler();
  $('message').focus();
}
$('btn-envoyer').onclick = envoyer;
$('btn-stop').onclick = () => ctrl && ctrl.abort();
$('message').addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); envoyer(); } });
function ajusterHauteur() { const t = $('message'); t.style.height = 'auto'; t.style.height = Math.min(t.scrollHeight, 260) + 'px'; }
$('message').addEventListener('input', ajusterHauteur);

$('btn-nouveau').onclick = () => {
  if (ctrl) ctrl.abort();
  messages = []; pieces = []; afficherPieces();
  $('fil-int').innerHTML = ''; $('fil-int').appendChild($('vide')); $('vide').hidden = false; $('message').focus();
};
$('btn-exporter').onclick = () => {
  if (!messages.length) return;
  const r = lireReglages();
  let s = '# Conversation Qwen — ' + new Date().toLocaleString('fr') + '\n\n';
  if (r.systeme.trim()) s += '## Instruction système\n\n' + r.systeme.trim() + '\n\n';
  for (const m of messages) s += '## ' + (m.role === 'user' ? 'Toi' : 'Qwen') + '\n\n' + m.content + '\n\n';
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([s], { type: 'text/markdown;charset=utf-8' }));
  a.download = 'conversation-qwen-' + new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-') + '.md';
  a.click(); URL.revokeObjectURL(a.href);
};

// ---- pièces jointes : fichiers texte lus tels quels, fichiers audio transcrits -----------------
function afficherPieces() {
  $('pieces').innerHTML = '';
  pieces.forEach((p, i) => {
    const s = document.createElement('span'); s.className = 'piece'; s.textContent = '📎 ' + p.nom + ' (' + p.contenu.length.toLocaleString('fr') + ' car.) ✕';
    s.style.cursor = 'pointer'; s.title = 'retirer'; s.onclick = () => { pieces.splice(i, 1); afficherPieces(); };
    $('pieces').appendChild(s);
  });
}
const EXT_AUDIO = __EXT_AUDIO__;
function extension(nom) { const i = nom.lastIndexOf('.'); return i < 0 ? '' : nom.slice(i).toLowerCase(); }
async function recevoirFichier(f) {
  if (!f) return;
  if (EXT_AUDIO.includes(extension(f.name)) || (f.type || '').startsWith('audio/')) {
    const texte = await transcrire(f, extension(f.name) || '.webm', f.name);
    if (texte) { pieces.push({ nom: f.name + ' (transcription)', contenu: texte }); afficherPieces(); }
    return;
  }
  const lecteur = new FileReader();
  lecteur.onload = () => { pieces.push({ nom: f.name, contenu: lecteur.result }); afficherPieces(); };
  lecteur.readAsText(f, 'utf-8');
}
$('btn-fichier').onclick = () => $('fichier').click();
$('fichier').onchange = e => { for (const f of e.target.files) recevoirFichier(f); e.target.value = ''; };
const comp = $('composeur');
comp.ondragover = e => { e.preventDefault(); comp.classList.add('sur'); };
comp.ondragleave = () => comp.classList.remove('sur');
comp.ondrop = e => { e.preventDefault(); comp.classList.remove('sur'); for (const f of e.dataTransfer.files) recevoirFichier(f); };

async function transcrire(blob, ext, nom) {
  $('aide').textContent = 'Transcription de ' + nom + '… (le premier appel charge Whisper, compter jusqu\'à une minute)';
  $('p-whisper').className = 'pastille encours';
  try {
    const rep = await fetch('/api/transcrire?ext=' + encodeURIComponent(ext), { method: 'POST', headers: {'Content-Type': 'application/octet-stream'}, body: blob });
    const j = await rep.json();
    if (!rep.ok || j.erreur) throw new Error(j.erreur || rep.statusText);
    $('aide').textContent = 'Transcrit : ' + nom + ' (' + j.texte.length + ' caractères, ' + j.duree + ' s)';
    etat();
    return j.texte;
  } catch (e) { $('aide').textContent = 'Transcription impossible : ' + e.message; etat(); return ''; }
}

// ---- dictée : MediaRecorder → /api/transcrire → texte inséré dans le message (pas d'envoi automatique) --
$('btn-micro').onclick = async () => {
  if (enregistreur) { enregistreur.stop(); return; }
  if (!navigator.mediaDevices || !window.isSecureContext) { $('aide').textContent = "Le micro n'est autorisé qu'en http://localhost (ou en HTTPS) : depuis un autre appareil, dépose plutôt un fichier audio."; return; }
  let flux;
  try { flux = await navigator.mediaDevices.getUserMedia({ audio: true }); }
  catch (e) { $('aide').textContent = 'Micro inaccessible : ' + e.message; return; }
  const type = ['audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/webm', 'audio/mp4'].find(t => MediaRecorder.isTypeSupported(t)) || '';
  const morceaux = [];
  enregistreur = new MediaRecorder(flux, type ? { mimeType: type } : {});
  enregistreur.ondataavailable = e => e.data.size && morceaux.push(e.data);
  enregistreur.onstop = async () => {
    flux.getTracks().forEach(t => t.stop());
    $('btn-micro').classList.remove('actif'); $('btn-micro').textContent = '🎤 Dicter'; chrono(false); $('chrono').textContent = '';
    enregistreur = null;
    const blob = new Blob(morceaux, { type: type || 'audio/webm' });
    const ext = type.includes('ogg') ? '.ogg' : type.includes('mp4') ? '.mp4' : '.webm';
    const texte = await transcrire(blob, ext, 'dictée');
    if (texte) { const t = $('message'); t.value = (t.value.trim() ? t.value.replace(/\s+$/, '') + ' ' : '') + texte; ajusterHauteur(); t.focus(); }
  };
  enregistreur.start();
  $('btn-micro').classList.add('actif'); $('btn-micro').textContent = '⏹ Arrêter la dictée'; chrono(true, $('chrono'));
  $('aide').textContent = 'Enregistrement… clique à nouveau pour arrêter.';
};

etat(); setInterval(etat, 30000); $('message').focus();
</script></body></html>
"""


# ---------------------------------------------------------------------------------------------------
# Logique serveur pure (testée dans tests/test_qwen_web.py)

def construire_requete(messages, systeme, reflexion, max_tokens, temperature):
    """Corps de la requête LM Studio : fil complet, instruction système en tête, tour assistant pré-rempli si réflexion coupée.

    Constaté sur LM Studio avec Qwen3.8 : ni `/no_think`, ni `reasoning_effort`, ni `enable_thinking` ne coupent la
    réflexion ; un tour assistant qui commence par un bloc <think> vide, si (le modèle continue ce tour sans réfléchir).
    """
    fil = [dict(m) for m in messages if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str)]
    if not reflexion:
        fil.append({"role": "assistant", "content": PREFILL_SANS_REFLEXION})
    if (systeme or "").strip():
        fil.insert(0, {"role": "system", "content": systeme.strip()})
    try:
        max_tokens = int(max_tokens)
    except (TypeError, ValueError):
        max_tokens = resumer.MAX_TOKENS
    try:
        temperature = float(temperature)
    except (TypeError, ValueError):
        temperature = 0.3
    return {
        "model": resumer.IDENTIFIANT,
        "messages": fil,
        "max_tokens": max(MAX_TOKENS_MIN, min(MAX_TOKENS_MAX, max_tokens)),
        "temperature": max(0.0, min(TEMPERATURE_MAX, temperature)),
        "stream": True,
    }


def ecrire_journal(messages, systeme, reponse, reflexion, reglages, dossier=None, quand=None):
    """Un fichier Markdown par échange, nommé par la date : la question n'est jamais perdue.

    Le dernier message utilisateur est la question du jour ; les tours précédents sont donnés comme contexte.
    Deux échanges terminés au même instant (deux PC) : jamais d'écrasement, on suffixe -2, -3…
    """
    dossier = Path(dossier) if dossier else JOURNAL
    dossier.mkdir(exist_ok=True)
    quand = quand or dt.datetime.now()
    question = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
    precedents = messages[:-1] if messages and messages[-1].get("role") == "user" else messages
    parties = [
        f"# Échange Qwen ({resumer.IDENTIFIANT}) — {quand.strftime('%d/%m/%Y %H:%M:%S')}",
        "",
        f"réglages : réflexion : {'oui' if reglages.get('reflexion') else 'non'} · max_tokens : {reglages.get('max_tokens')}"
        f" · température : {reglages.get('temperature')}",
    ]
    if (systeme or "").strip():
        parties += ["", "## Instruction système", "", systeme.strip()]
    if precedents:
        parties += ["", "## Tours précédents", ""]
        for m in precedents:
            parties += [f"**{'Toi' if m.get('role') == 'user' else 'Qwen'}** :", "", m.get("content", "").strip(), ""]
    parties += ["", "## Question", "", question.strip() or "(vide)", "", "## Réponse", "", reponse.strip()]
    if reflexion.strip():
        parties += ["", "## Réflexion du modèle", "", reflexion.strip()]
    base = quand.strftime("%Y-%m-%d_%H%M%S")
    for n in range(1, 1000):
        nom = base + ("" if n == 1 else f"-{n}") + ".md"
        try:
            with open(dossier / nom, "x", encoding="utf-8") as f:  # "x" : échoue si le fichier existe déjà
                f.write("\n".join(parties) + "\n")
            return nom
        except FileExistsError:
            continue
    raise RuntimeError(f"journal : impossible de trouver un nom libre pour {base}")


def titre_journal(fichier):
    """Première ligne de la section Question (ou Consigne, pour les anciens fichiers)."""
    for bloc in fichier.read_text(encoding="utf-8").split("\n## ")[1:]:
        if bloc.startswith(("Question", "Consigne")) and "\n" in bloc:
            return bloc.split("\n", 1)[1].strip().splitlines()[0][:120]
    return ""


# ---------------------------------------------------------------------------------------------------
# Transcription : Whisper chargé une fois (au premier usage), en réutilisant l'outil stt.

_whisper = {"modele": None, "etat": "pret", "erreur": "", "verrou": threading.Lock()}
_verrou_transcription = threading.Lock()   # une transcription à la fois : le GPU n'en fait pas deux plus vite
_verrou_chargement_mac = threading.Lock()  # un seul « Charger brain » à la fois : deux SSH se marcheraient dessus


def _stt():
    if str(STT_DOSSIER) not in sys.path:
        sys.path.insert(0, str(STT_DOSSIER))
    import transcrire  # noqa: E402  — D:\AudioToTxt\stt\transcrire.py
    return transcrire


def charger_whisper():
    """Charge le modèle Whisper une seule fois ; les appels suivants renvoient l'instance résidente."""
    with _whisper["verrou"]:
        if _whisper["modele"] is not None:
            return _whisper["modele"]
        _whisper["etat"] = "chargement"
        try:
            stt = _stt()
            local = next((p for p in WHISPER_MODELES if p.is_dir()), None)
            _whisper["modele"] = stt.charger_whisper(str(local) if local else stt.MODELE_DEFAUT, device="auto")
            _whisper["etat"] = "charge"
        except (Exception, SystemExit) as exc:  # noqa: BLE001 — l'outil signale ses échecs par sys.exit
            _whisper["etat"], _whisper["erreur"] = "absent", str(exc) or repr(exc)
            raise RuntimeError(_whisper["erreur"]) from exc
        return _whisper["modele"]


def transcrire_audio(octets, suffixe, modele=None):
    """Octets audio → texte. Le fichier temporaire est effacé quoi qu'il arrive."""
    if not octets:
        raise ValueError("audio vide")
    if suffixe.lower() not in EXTENSIONS_AUDIO:
        raise ValueError(f"format audio non pris en charge : {suffixe}")
    modele = modele or charger_whisper()
    fd, chemin = tempfile.mkstemp(suffix=suffixe.lower(), prefix="qwen_web_")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(octets)
        with _verrou_transcription:  # deux PC en même temps : le second attend son tour
            return _stt().transcrire_fichier(modele, chemin, WHISPER_LANGUE)
    finally:
        try:
            os.unlink(chemin)
        except OSError:
            pass


def lire_modeles():
    with urllib.request.urlopen(f"{BASE}/api/v0/models", timeout=5) as rep:
        return json.load(rep).get("data", [])


def page_html():
    return (PAGE.replace("__SCRIPT_MD__", SCRIPT_MD)
                .replace("__MAX_TOKENS__", str(resumer.MAX_TOKENS))
                .replace("__EXT_AUDIO__", json.dumps(sorted(EXTENSIONS_AUDIO))))


class Relais(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # une ligne par requête suffit, sans le bruit des GET d'état
        if "/api/etat" not in (args[0] if args else ""):
            super().log_message(fmt, *args)

    def _json(self, code, obj):
        corps = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def _corps(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def _html(self, corps):
        octets = corps.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(octets)))
        self.end_headers()
        self.wfile.write(octets)

    def do_GET(self):
        if self.path == "/":
            self._html(page_html())
        elif self.path == "/journal":
            self._page_journal()
        elif self.path.startswith("/journal/"):
            self._fichier_journal(self.path[len("/journal/"):])
        elif self.path == "/api/etat":
            compte = f"{resumer.MAC_USER}@{resumer.MAC_IP}"
            whisper = {"whisper": _whisper["etat"], "whisper_erreur": _whisper["erreur"]}
            if not STT_DOSSIER.is_dir():
                whisper = {"whisper": "absent", "whisper_erreur": f"outil introuvable : {STT_DOSSIER}"}
            try:
                modeles = lire_modeles()
                brain = any(m.get("id") == resumer.IDENTIFIANT and m.get("state") == "loaded" for m in modeles)
                self._json(200, {"serveur": True, "brain": brain, "base": BASE, "compte": compte, **whisper})
            except (urllib.error.URLError, OSError, ValueError):
                self._json(200, {"serveur": False, "brain": False, "base": BASE, "compte": compte, **whisper})
        else:
            self.send_error(404)

    def _page_journal(self):
        fichiers = sorted(JOURNAL.glob("*.md"), reverse=True) if JOURNAL.is_dir() else []
        lignes = [f'<li><a href="/journal/{f.name}">{f.stem}</a> — {html.escape(titre_journal(f))}</li>' for f in fichiers]
        self._html(f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Journal Qwen</title>
<style>body{{font:14px/1.6 system-ui,sans-serif;max-width:960px;margin:0 auto;padding:20px 16px;color:#1c1e21}}li{{margin:4px 0}}</style>
</head><body><h1>Journal des échanges</h1><p><a href="/">← retour</a> · dossier : <code>{html.escape(str(JOURNAL))}</code></p>
<ul>{"".join(lignes) or "<li>(vide)</li>"}</ul></body></html>""")

    def _fichier_journal(self, nom):
        f = JOURNAL / nom
        if "/" in nom or ".." in nom or not f.is_file():
            self.send_error(404)
            return
        self._html(f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>{html.escape(nom)}</title>
<style>body{{font:14px/1.6 system-ui,sans-serif;max-width:960px;margin:0 auto;padding:20px 16px;color:#1c1e21}}pre{{white-space:pre-wrap}}</style>
</head><body><p><a href="/journal">← journal</a></p><pre>{html.escape(f.read_text(encoding="utf-8"))}</pre></body></html>""")

    def do_POST(self):
        if self.path == "/api/chat":
            self._chat()
        elif self.path == "/api/charger":
            self._charger()
        elif self.path.startswith("/api/transcrire"):
            self._transcrire()
        else:
            self.send_error(404)

    def _chat(self):
        d = self._corps()
        messages = d.get("messages") or []
        reglages = {"reflexion": bool(d.get("reflexion", True)), "max_tokens": d.get("max_tokens"), "temperature": d.get("temperature")}
        requete = construire_requete(messages, d.get("systeme") or "", reglages["reflexion"], reglages["max_tokens"], reglages["temperature"])
        reglages["max_tokens"], reglages["temperature"] = requete["max_tokens"], requete["temperature"]
        req = urllib.request.Request(f"{BASE}/v1/chat/completions", data=json.dumps(requete).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        reponse, reflexion = [], []
        try:
            with urllib.request.urlopen(req, timeout=resumer.TIMEOUT_HTTP) as rep:
                for ligne in rep:  # LM Studio envoie du SSE : on le retransmet tel quel, en le lisant au passage
                    self.wfile.write(ligne)
                    self.wfile.flush()
                    if ligne.startswith(b"data: {"):
                        try:
                            delta = json.loads(ligne[6:])["choices"][0].get("delta") or {}
                        except (ValueError, KeyError, IndexError):
                            continue
                        if delta.get("content"):
                            reponse.append(delta["content"])
                        if delta.get("reasoning_content"):
                            reflexion.append(delta["reasoning_content"])
            if reponse:
                nom = ecrire_journal(messages, d.get("systeme") or "", "".join(reponse), "".join(reflexion), reglages)
                self.wfile.write(f"data: {json.dumps({'journal': nom})}\n\n".encode("utf-8"))
                self.wfile.flush()
        except urllib.error.HTTPError as exc:
            msg = exc.read().decode(errors="replace")[:500]
            self.wfile.write(f"data: {json.dumps({'erreur': f'HTTP {exc.code} : {msg}'})}\n\n".encode("utf-8"))
        except (urllib.error.URLError, OSError) as exc:
            try:
                self.wfile.write(f"data: {json.dumps({'erreur': str(exc)})}\n\n".encode("utf-8"))
            except OSError:
                pass  # le navigateur a coupé (bouton Arrêter)

    def _transcrire(self):
        from urllib.parse import parse_qs, urlparse
        ext = (parse_qs(urlparse(self.path).query).get("ext") or [".webm"])[0]
        n = int(self.headers.get("Content-Length") or 0)
        octets = self.rfile.read(n)
        debut = dt.datetime.now()
        try:
            texte = transcrire_audio(octets, ext)
        except ValueError as exc:
            self._json(400, {"erreur": str(exc)})
            return
        except Exception as exc:  # noqa: BLE001 — chargement Whisper, décodage audio : on renvoie le message brut
            self._json(500, {"erreur": str(exc) or repr(exc)})
            return
        self._json(200, {"texte": texte, "duree": round((dt.datetime.now() - debut).total_seconds(), 1)})

    def _charger(self):
        d = self._corps()
        if not _verrou_chargement_mac.acquire(blocking=False):
            self._json(200, {"ok": False, "journal": "", "erreur": "un chargement est déjà en cours depuis un autre navigateur : réessaie dans une minute."})
            return
        journal = []
        original = print
        try:
            # preparer_mac écrit sa progression avec print : on la capture pour la renvoyer au navigateur.
            # (print est remplacé globalement dans resumer : d'où le verrou, deux appels mélangeraient leurs journaux.)
            resumer.print = lambda *a, **k: journal.append(" ".join(str(x) for x in a))
            client = resumer.ssh_ouvrir(d.get("mdp") or "")
            try:
                resumer.preparer_mac(client)
            finally:
                client.close()
            self._json(200, {"ok": True, "journal": "\n".join(journal)})
        except SystemExit as exc:  # resumer.py signale ses échecs par sys.exit(message)
            self._json(200, {"ok": False, "journal": "\n".join(journal), "erreur": str(exc)})
        except Exception as exc:  # noqa: BLE001
            self._json(200, {"ok": False, "journal": "\n".join(journal), "erreur": repr(exc)})
        finally:
            resumer.print = original
            _verrou_chargement_mac.release()


def adresse_ecoute(reseau):
    """127.0.0.1 = ce PC seulement (défaut) ; 0.0.0.0 = aussi les autres appareils du réseau local."""
    return "0.0.0.0" if reseau else "127.0.0.1"


def adresses_locales():
    """Les IP de ce PC sur le réseau local, à donner aux autres appareils."""
    import socket
    try:
        return sorted({a[4][0] for a in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)} - {"127.0.0.1"})
    except OSError:
        return []


def main():
    ap = argparse.ArgumentParser(description="Interface web locale pour le profil brain.")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--sans-navigateur", action="store_true", help="ne pas ouvrir le navigateur au démarrage")
    ap.add_argument("--reseau", action="store_true",
                    help="accepter aussi les autres appareils du réseau local (pare-feu Windows à ouvrir sur le port)")
    args = ap.parse_args()
    serveur = ThreadingHTTPServer((adresse_ecoute(args.reseau), args.port), Relais)
    url = f"http://localhost:{args.port}"
    print(f"Qwen web : {url}   (relais vers {BASE}, Whisper via {STT_DOSSIER}, Ctrl+C pour arrêter)")
    if args.reseau:
        for ip in adresses_locales():
            print(f"  depuis un autre appareil de la maison : http://{ip}:{args.port}")
        print("  (micro et boutons Copier : seulement en http://localhost ou en HTTPS, les navigateurs l'imposent)")
    if not args.sans_navigateur:
        webbrowser.open(url)
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        print("\narrêt.")


if __name__ == "__main__":
    main()
