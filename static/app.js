const $ = (id) => document.getElementById(id);
let selectedItems = [];
function notice(message, danger = false) {
  $('notice').textContent = message;
  $('notice').className = `alert ${danger ? 'alert-danger' : 'alert-secondary'}`;
}
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {
    method: 'POST', headers: {'Content-Type': 'application/json', 'X-Bahload': '1'}, body: JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) { const error = new Error(data.detail || 'Não foi possível concluir.'); error.status = response.status; error.data = data; throw error; }
  return data;
}
function element(tag, className, text) {
  const node = document.createElement(tag); node.className = className || ''; if (text !== undefined) node.textContent = text; return node;
}
function setFormats() {
  const audio = $('kind').value === 'audio';
  $('format').replaceChildren(...(audio ? ['mp3','m4a','wav','opus'] : ['mp4','mkv','webm']).map(v => new Option(v.toUpperCase(), v)));
  $('quality').replaceChildren(...(audio ? [['128 kbps','128'],['192 kbps','192'],['320 kbps','320']] : [['Melhor disponível','best'],['Até 1080p','1080'],['Até 720p','720'],['Até 480p','480']]).map(([label,v]) => new Option(label,v)));
  if (audio) $('quality').value = '192';
  updateQuality();
}
function updateQuality() {
  const wav = $('format').value === 'wav'; $('quality').disabled = wav;
  $('quality-note').textContent = $('kind').value === 'video' ? 'Resolução máxima: usa a melhor opção disponível até esse limite, sem ampliar. MKV aceita mais codecs.' : wav ? 'WAV preserva áudio PCM sem compressão; bitrate não se aplica.' : 'Bitrate de saída solicitado. A qualidade original da fonte continua sendo o limite.';
}
$('kind').addEventListener('change', setFormats); $('format').addEventListener('change', updateQuality); setFormats();
function updateSelection() {
  const boxes = [...$('videos').querySelectorAll('input')];
  const count = boxes.filter(b => b.checked).length;
  $('selection-count').textContent = `${count} de ${boxes.length} selecionados`;
  $('enqueue').disabled = count === 0 || !$('destination').value;
  $('toggle-all').textContent = count === boxes.length ? 'Desmarcar todos' : 'Marcar todos';
}
$('toggle-all').onclick = () => { const boxes = [...$('videos').querySelectorAll('input')]; const checked = !boxes.every(b => b.checked); boxes.forEach(b => b.checked = checked); updateSelection(); };
$('choose-folder').onclick = async () => {
  $('choose-folder').disabled = true;
  $('choose-folder').textContent = 'Escolhendo…';
  try {
    const result = await api('/api/destination', {});
    if (result.destination) $('destination').value = result.destination;
    updateSelection();
  } catch (error) { notice(error.message, true); }
  finally { $('choose-folder').disabled = false; $('choose-folder').textContent = 'Escolher pasta'; }
};
$('inspect-form').addEventListener('submit', async event => {
  event.preventDefault(); $('inspect').disabled = true; $('inspect').textContent = 'Buscando…';
  try {
    const result = await api('/api/inspect', {url: $('url').value}); selectedItems = result.items;
    $('selection-title').textContent = result.title; $('videos').replaceChildren();
    result.items.forEach((item, i) => { const label = element('label', 'video-option'); const box = element('input', 'form-check-input'); box.type = 'checkbox'; box.checked = true; box.value = i; box.onchange = updateSelection; const img = element('img'); img.src = item.thumbnail; img.alt = ''; img.loading = 'lazy'; label.append(box, img, element('span', 'small', item.title)); $('videos').append(label); });
    $('selection').classList.remove('d-none'); updateSelection();
    notice(result.limited ? 'Foram carregados até 500 itens desta playlist.' : 'Conteúdo encontrado. Escolha as opções e inicie o download.');
  } catch (error) { notice(error.message, true); }
  finally { $('inspect').disabled = false; $('inspect').textContent = 'Adicionar'; }
});
$('enqueue').onclick = async () => {
  if (!$('destination').value) { notice('Escolha a pasta de destino antes de baixar.', true); return; }
  const items = [...$('videos').querySelectorAll('input:checked')].map(b => selectedItems[Number(b.value)]);
  const body = {items, options: {kind: $('kind').value, format: $('format').value, bitrate: $('kind').value === 'audio' ? Number($('quality').value) : 192, resolution: $('kind').value === 'video' ? $('quality').value : 'best', destination: $('destination').value, retries: Number($('retries').value)}};
  $('enqueue').disabled = true;
  try {
    try { await api('/api/jobs', body); }
    catch (error) { if (error.status !== 409) throw error; if (!window.confirm('Há vídeos repetidos nesta seleção ou já presentes na fila. Deseja baixar outra cópia?')) return; await api('/api/jobs', {...body, allow_duplicates: true}); }
    notice('Itens adicionados à fila.');
  } catch (error) { notice(error.message, true); }
  finally { updateSelection(); }
};
const statuses = {queued:['Na fila','primary'], downloading:['Baixando','warning'], processing:['Processando','warning'], retrying:['Aguardando retry','warning'], completed:['Concluído','success'], error:['Erro','danger'], cancelling:['Cancelando…','secondary'], cancelled:['Cancelado','secondary']};
function size(bytes) { if (!bytes) return '—'; return bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${(bytes / 1024).toFixed(1)} KB`; }
const cards = new Map();
function renderJobs(jobs) {
  $('job-count').textContent = jobs.length;
  if (!jobs.length) return;
  if (!cards.size) $('jobs').replaceChildren();
  jobs.forEach(job => {
    let card = cards.get(job.id);
    const signature = JSON.stringify(job);
    if (card?.dataset.signature === signature) return;
    if (!card) { card = element('article', 'job'); cards.set(job.id, card); $('jobs').prepend(card); }
    card.dataset.signature = signature; card.replaceChildren();
    const top = element('div', 'd-flex gap-3 align-items-start'); const img = element('img'); img.src = job.thumbnail; img.alt = ''; img.loading = 'lazy';
    const content = element('div', 'flex-grow-1 min-w-0'); const heading = element('div', 'd-flex flex-wrap gap-2 justify-content-between');
    const [label, color] = statuses[job.status] || [job.status,'secondary'];
    heading.append(element('div','job-title',job.title), element('span',`badge text-bg-${color} align-self-start`,label));
    content.append(heading, element('div','small text-secondary mt-1',`${job.options.format.toUpperCase()} · Tentativa ${job.attempt} · ${Math.round(job.progress)}% · ${size(job.downloaded)} / ${size(job.total)}${job.speed ? ` · ${size(job.speed)}/s` : ''}`));
    const progress = element('div','progress mt-3'); progress.setAttribute('role','progressbar'); progress.setAttribute('aria-label',`Progresso de ${job.title}`); progress.setAttribute('aria-valuenow',Math.round(job.progress)); progress.setAttribute('aria-valuemin','0'); progress.setAttribute('aria-valuemax','100'); const bar = element('div','progress-bar'); bar.style.width = `${job.progress}%`; progress.append(bar); content.append(progress);
    if (job.error) content.append(element('p','job-error mt-2 mb-0',job.error));
    const actions = element('div','mt-3 d-flex gap-2');
    if (['error','cancelled'].includes(job.status) || ['queued','downloading','processing','retrying'].includes(job.status)) {
      const retry = ['error','cancelled'].includes(job.status); const button = element('button','btn btn-sm btn-outline-dark',retry ? 'Tentar novamente' : 'Cancelar');
      button.onclick = async () => { button.disabled = true; try { await api(`/api/jobs/${job.id}/${retry ? 'retry' : 'cancel'}`, {}); } catch(error) { notice(error.message,true); button.disabled = false; } }; actions.append(button);
    }
    if (job.status === 'completed') content.append(element('p','job-path mt-2 mb-0',`Salvo em: ${job.path}`));
    content.append(actions); top.append(img,content); card.append(top);
  });
}
const stream = new EventSource('/api/events');
stream.onopen = () => $('connection').textContent = '● Atualização ao vivo';
stream.onmessage = event => renderJobs(JSON.parse(event.data));
stream.onerror = () => $('connection').textContent = 'Reconectando…';
api('/api/config').then(config => {
  const missing = []; if (!config.ffmpeg) missing.push('FFmpeg e FFprobe não encontrados no PATH.'); if (!config.javascript) missing.push('Instale Deno ou Node.js para o yt-dlp.');
  if (missing.length) { $('dependencies').textContent = missing.join(' '); $('dependencies').classList.remove('d-none'); }
}).catch(error => notice(error.message,true));
