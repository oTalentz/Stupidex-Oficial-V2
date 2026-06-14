const state={user:null,sessions:[],sessionId:null,workspaces:[],workspaceId:null,models:[],approvalId:null,authMode:'login',rightTab:'files',sending:false,rightOpen:window.matchMedia('(min-width: 1024px)').matches};
const $=id=>document.getElementById(id);
const api=async(path,options={})=>{const res=await fetch(path,{credentials:'include',headers:{...(options.body instanceof FormData?{}:{'Content-Type':'application/json'}),...(options.headers||{})},...options});let data={};try{data=await res.json()}catch{}if(!res.ok&&res.status!==202)throw new Error(data.error||`Erro ${res.status}`);return {data,status:res.status,res};};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const toast=(msg,error=false)=>{const el=$('toast');el.textContent=msg;el.className=`fixed right-4 bottom-4 z-[100] max-w-sm border rounded-xl px-4 py-3 text-sm shadow-2xl ${error?'bg-red-950 border-red-500/30 text-red-200':'bg-zinc-900 border-white/10'}`;el.classList.remove('hidden');setTimeout(()=>el.classList.add('hidden'),3500)};
const modal=(id,show=true)=>{const el=$(id);el.classList.toggle('hidden',!show);if(show)el.classList.add('flex');else el.classList.remove('flex')};
const providerVisuals={
  openai:{mark:'AI',color:'bg-emerald-500/10 text-emerald-300 border-emerald-500/20'},
  anthropic:{mark:'CL',color:'bg-orange-500/10 text-orange-300 border-orange-500/20'},
  gemini:{mark:'GE',color:'bg-blue-500/10 text-blue-300 border-blue-500/20'},
  deepseek:{mark:'DS',color:'bg-cyan-500/10 text-cyan-300 border-cyan-500/20'},
  openrouter:{mark:'OR',color:'bg-violet-500/10 text-violet-300 border-violet-500/20'},
};

function formatText(text){
  const blocks=[];
  let html=String(text??'').replace(/```([\w-]*)\n([\s\S]*?)```/g,(_,lang,code)=>{
    const index=blocks.push(`<pre><code class="language-${esc(lang||'text')}">${esc(code.replace(/\n$/,''))}</code></pre>`)-1;
    return `\u0000CODE${index}\u0000`;
  });
  html=esc(html);
  html=html.replace(/`([^`]+)`/g,'<code>$1</code>');
  html=html.replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>');
  html=html.replace(/\n/g,'<br>');
  html=html.replace(/\u0000CODE(\d+)\u0000/g,(_,index)=>blocks[Number(index)]||'');
  return html;
}

function setBusy(busy){
  state.sending=busy;
  $('send-btn').disabled=busy;
  $('composer').disabled=busy;
  $('send-btn').classList.toggle('is-busy',busy);
  $('send-btn').innerHTML=busy?'<i class="ph ph-spinner animate-spin"></i>':'<i class="ph-fill ph-arrow-up"></i>';
}

function setMode(mode,persist=false){
  $('mode-select').value=mode;
  document.querySelectorAll('[data-mode]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.mode===mode)));
  if(persist&&state.sessionId){
    api(`/api/sessions/${state.sessionId}`,{method:'PATCH',body:JSON.stringify({mode})}).catch(error=>toast(error.message,true));
  }
}

function setRightPanel(open){
  state.rightOpen=open;
  $('right-panel').classList.toggle('panel-open',open);
  $('right-panel').classList.toggle('panel-closed',!open);
  $('toggle-right').setAttribute('aria-expanded',String(open));
}

function setLeftPanel(open){
  $('left-sidebar').classList.toggle('-translate-x-full',!open);
  $('mobile-backdrop').classList.toggle('hidden',!open);
}

function resizeComposer(){
  const composer=$('composer');
  composer.style.height='auto';
  composer.style.height=`${Math.min(composer.scrollHeight,180)}px`;
}

async function init(){
  try{
    state.user=(await api('/api/auth/me')).data;
  }catch{
    $('auth-screen').classList.remove('hidden');
    $('app').classList.add('hidden');
    return;
  }
  $('auth-screen').classList.add('hidden');
  $('app').classList.remove('hidden');
  $('profile-name').textContent=state.user.username;
  setRightPanel(state.rightOpen);
  const results=await Promise.allSettled([loadModels(),loadSessions(),loadWorkspaces()]);
  results.filter(result=>result.status==='rejected').forEach(result=>toast(result.reason?.message||'Falha ao carregar a interface',true));
  if(state.sessions[0])await selectSession(state.sessions[0].id);
  else await createSession();
}

async function loadModels(){
  state.models=(await api('/api/models')).data;
  renderModelPicker();
  const configured=state.models.find(model=>model.id===state.user?.model);
  const selected=configured||state.models.find(model=>model.recommended)||state.models[0];
  if(selected)selectModel(selected.id,false);
}

function renderModelPicker(){
  const groups=new Map();
  state.models.forEach(model=>{
    if(!groups.has(model.provider))groups.set(model.provider,[]);
    groups.get(model.provider).push(model);
  });
  $('model-options').innerHTML=[...groups.entries()].map(([provider,models])=>{
    const visual=providerVisuals[provider]||{mark:'IA',color:'bg-zinc-800 text-zinc-300 border-white/10'};
    return `<section class="mb-1 last:mb-0">
      <div class="px-2 pt-2 pb-1.5 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-600">
        <span>${esc(models[0].provider_label||provider)}</span>
        <span class="h-px flex-1 bg-white/5"></span>
      </div>
      <div class="space-y-1">${models.map(model=>`<button type="button" role="option" aria-selected="false" data-model-id="${esc(model.id)}" class="model-option w-full flex items-center gap-3 p-2.5 rounded-xl border border-transparent hover:bg-white/[0.045] transition-all text-left">
        <span class="provider-mark w-9 h-9 rounded-xl border ${visual.color} grid place-items-center text-[10px] font-bold flex-shrink-0">${visual.mark}</span>
        <span class="min-w-0 flex-1">
          <span class="flex items-center gap-2">
            <span class="text-xs font-semibold text-zinc-200 truncate">${esc(model.label)}</span>
            <span class="text-[9px] text-zinc-500 bg-zinc-800/80 rounded-full px-1.5 py-0.5 whitespace-nowrap">${esc(model.badge||'')}</span>
          </span>
          <span class="block text-[10px] text-zinc-500 mt-0.5 truncate">${esc(model.description||'')}</span>
        </span>
        <span class="model-check w-5 h-5 rounded-full bg-violet-500/20 text-violet-300 grid place-items-center flex-shrink-0"><i class="ph-bold ph-check text-[11px]"></i></span>
      </button>`).join('')}</div>
    </section>`;
  }).join('');
  document.querySelectorAll('[data-model-id]').forEach(button=>button.onclick=()=>selectModel(button.dataset.modelId));
}

function selectModel(id,close=true){
  const model=state.models.find(item=>item.id===id);
  if(!model)return;
  $('model-select').value=model.id;
  $('model-selected-label').textContent=model.label;
  $('model-selected-provider').textContent=model.provider_label||model.provider;
  document.querySelectorAll('[data-model-id]').forEach(button=>button.setAttribute('aria-selected',String(button.dataset.modelId===id)));
  if(close)toggleModelMenu(false);
}

function toggleModelMenu(open=$('model-menu').classList.contains('hidden')){
  $('model-menu').classList.toggle('hidden',!open);
  $('model-trigger').setAttribute('aria-expanded',String(open));
  $('model-caret').classList.toggle('rotate-180',open);
  if(open){
    requestAnimationFrame(()=>(document.querySelector('[data-model-id][aria-selected="true"]')||document.querySelector('[data-model-id]'))?.focus());
  }
}

function moveModelFocus(direction){
  const options=[...document.querySelectorAll('[data-model-id]')];
  if(!options.length)return;
  const current=options.indexOf(document.activeElement);
  options[(current+direction+options.length)%options.length].focus();
}

async function loadSessions(){
  state.sessions=(await api('/api/sessions')).data;
  renderSessions();
}

function renderSessions(){
  $('session-list').innerHTML=state.sessions.length?state.sessions.map(s=>`<button data-session="${s.id}" class="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-left ${s.id===state.sessionId?'bg-zinc-900 text-zinc-200':'text-zinc-400 hover:bg-zinc-900/60 hover:text-zinc-200'} transition-colors"><i class="ph ph-chat-teardrop text-zinc-500"></i><span class="truncate">${esc(s.title)}</span></button>`).join(''):'<p class="px-3 text-xs text-zinc-600">Nenhuma conversa.</p>';
  document.querySelectorAll('[data-session]').forEach(b=>b.onclick=()=>selectSession(b.dataset.session));
}

async function createSession(){
  const s=(await api('/api/sessions',{method:'POST',body:JSON.stringify({title:'Nova conversa',mode:$('mode-select').value})})).data;
  state.sessions.unshift(s);
  renderSessions();
  await selectSession(s.id);
}

async function selectSession(id){
  state.sessionId=id;
  const session=state.sessions.find(s=>s.id===id);
  $('top-title').textContent=session?.title||'Conversa';
  setMode(session?.mode||'chat');
  $('messages').innerHTML='';
  const messages=(await api(`/api/sessions/${id}/messages`)).data;
  if(!messages.length)renderWelcome();
  else{
    messages.forEach(renderMessage);
    scrollBottom();
  }
  renderSessions();
  if(window.innerWidth<768)setLeftPanel(false);
}

function renderWelcome(){
  $('messages').innerHTML=`<div class="welcome-state min-h-[52vh] flex flex-col items-center justify-center text-center space-y-6">
    <div class="w-16 h-16 rounded-2xl bg-zinc-900 border border-white/10 shadow-glow flex items-center justify-center">
      <i class="ph-bold ph-lightning text-3xl text-violet-500"></i>
    </div>
    <h1 class="text-3xl font-medium tracking-tight">Como posso ajudar você hoje?</h1>
    <p class="text-sm text-zinc-500 max-w-md">Converse, conecte um repositório ou use o modo Agente para analisar e modificar seu projeto.</p>
    <div class="grid sm:grid-cols-2 gap-3 max-w-lg w-full">
      <button class="quick glass-panel rounded-xl p-4 text-sm hover:bg-zinc-800/50 transition-colors text-left" data-q="Analise a arquitetura do projeto conectado">
        <i class="ph ph-magnifying-glass text-violet-400 text-lg mb-2 block"></i>
        Analisar projeto
      </button>
      <button class="quick glass-panel rounded-xl p-4 text-sm hover:bg-zinc-800/50 transition-colors text-left" data-q="Encontre e corrija os principais erros">
        <i class="ph ph-bug text-violet-400 text-lg mb-2 block"></i>
        Corrigir erros
      </button>
      <button class="quick glass-panel rounded-xl p-4 text-sm hover:bg-zinc-800/50 transition-colors text-left" data-q="Crie um plano de implementação detalhado">
        <i class="ph ph-list-checks text-violet-400 text-lg mb-2 block"></i>
        Planejar funcionalidade
      </button>
      <button class="quick glass-panel rounded-xl p-4 text-sm hover:bg-zinc-800/50 transition-colors text-left" data-q="Revise as alterações atuais do Git">
        <i class="ph ph-git-diff text-violet-400 text-lg mb-2 block"></i>
        Revisar código
      </button>
    </div>
  </div>`;
  document.querySelectorAll('.quick').forEach(b=>b.onclick=()=>{
    $('composer').value=b.dataset.q;
    $('composer').focus();
  });
}

function renderMessage(m){
  if($('messages').querySelector('.min-h-\\[52vh\\]'))$('messages').innerHTML='';
  const row=document.createElement('div');
  row.className=m.role==='user'?'flex justify-end animate-slide-up stagger-1':'flex gap-4 animate-slide-up stagger-2';
  row.innerHTML=m.role==='user'?`<div class="max-w-[80%] bg-zinc-900 border border-white/5 rounded-2xl rounded-tr-sm px-5 py-4 text-sm text-zinc-200">${formatText(m.content)}</div>`:`<div class="w-8 h-8 rounded-full bg-transparent flex flex-shrink-0 justify-center mt-1"><i class="ph-bold ph-lightning text-violet-500 text-xl"></i></div><div class="message flex-1 space-y-4"><div class="text-sm text-zinc-300 leading-relaxed">${formatText(m.content)}</div></div>`;
  $('messages').appendChild(row);
  return row;
}

const scrollBottom=()=>requestAnimationFrame(()=>$('chat-feed').scrollTo({top:$('chat-feed').scrollHeight,behavior:'smooth'}));

async function send(){
  const text=$('composer').value.trim();
  if(!text||!state.sessionId||state.sending)return;
  const session=state.sessions.find(item=>item.id===state.sessionId);
  const shouldRename=session?.title==='Nova conversa';
  $('composer').value='';
  resizeComposer();
  setBusy(true);
  renderMessage({role:'user',content:text});
  const row=renderMessage({role:'assistant',content:'...'});
  const body=row.querySelector('.message');
  body.innerHTML='<div class="shimmer h-4 rounded w-full"></div>';
  scrollBottom();

  try{
    const {res}=await api(`/api/sessions/${state.sessionId}/chat`,{method:'POST',body:JSON.stringify({message:text,model:$('model-select').value,mode:$('mode-select').value})});
    const reader=res.body.getReader(),decoder=new TextDecoder();
    let buffer='',full='';
    body.innerHTML='';

    while(true){
      const {value,done}=await reader.read();
      if(done)break;
      buffer+=decoder.decode(value,{stream:true});
      const blocks=buffer.split('\n\n');
      buffer=blocks.pop();

      for(const block of blocks){
        const event=(block.match(/^event: (.+)$/m)||[])[1];
        const raw=(block.match(/^data: (.+)$/m)||[])[1];
        if(!raw)continue;
        const data=JSON.parse(raw);
        if(event==='delta'){
          full+=data.text;
          body.innerHTML=`<div class="text-sm text-zinc-300 leading-relaxed">${formatText(full)}</div>`;
          scrollBottom();
        }
        if(event==='error')throw new Error(data.error);
      }
    }
    if(shouldRename){
      const title=text.replace(/\s+/g,' ').slice(0,60);
      await api(`/api/sessions/${state.sessionId}`,{method:'PATCH',body:JSON.stringify({title})});
      $('top-title').textContent=title;
    }
    await loadSessions();
  }catch(e){
    body.innerHTML=`<span class="text-red-400">${esc(e.message)}</span>`;
  }finally{
    setBusy(false);
    $('composer').focus();
  }
}

async function loadWorkspaces(){
  state.workspaces=(await api('/api/workspaces')).data;
  renderWorkspaces();
  if(!state.workspaceId&&state.workspaces[0])await selectWorkspace(state.workspaces[0].id);
  if(!state.workspaces.length)updateContext(0);
}

function updateContext(fileCount){
  const workspace=state.workspaces.find(item=>item.id===state.workspaceId);
  const pill=$('context-pill');
  if(!workspace){
    pill.classList.add('hidden');
    pill.classList.remove('flex');
    return;
  }
  $('context-label').textContent=`${workspace.name} · ${fileCount} ${fileCount===1?'arquivo':'arquivos'}`;
  pill.classList.remove('hidden');
  pill.classList.add('flex');
}

function renderWorkspaces(){
  $('workspace-list').innerHTML=state.workspaces.length?state.workspaces.map(w=>`<button data-workspace="${w.id}" class="w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm ${w.id===state.workspaceId?'bg-zinc-900':'text-zinc-400 hover:bg-zinc-900/50 hover:text-zinc-200'} group transition-colors">
    <div class="flex items-center gap-2 truncate">
      <i class="ph ph-github-logo text-zinc-400"></i>
      <span class="truncate">${esc(w.name)}</span>
    </div>
    ${w.git_branch?`<div class="flex items-center gap-1.5 opacity-60"><span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span><span class="text-[10px] font-mono">${esc(w.git_branch)}</span></div>`:''}
  </button>`).join(''):'<p class="px-3 text-xs text-zinc-600">Nenhum projeto.</p>';
  document.querySelectorAll('[data-workspace]').forEach(b=>b.onclick=()=>selectWorkspace(b.dataset.workspace));
}

async function selectWorkspace(id){
  state.workspaceId=id;
  const w=state.workspaces.find(x=>x.id===id);
  $('top-project').textContent=w?w.name:'Nenhum projeto';
  renderWorkspaces();
  await loadTree();
}

async function loadTree(){
  if(!state.workspaceId){$('file-tree').innerHTML='';updateContext(0);return}
  try{
    const items=(await api(`/api/workspaces/${state.workspaceId}/tree`)).data;
    const q=$('file-search').value.toLowerCase();
    $('file-tree').innerHTML=items.filter(x=>!q||x.path.toLowerCase().includes(q)).map(x=>`<button data-file="${esc(x.path)}" ${x.type==='directory'?'disabled':''} class="w-full text-left px-2 py-1.5 rounded text-xs ${x.type==='directory'?'text-zinc-600':'text-zinc-400 hover:bg-zinc-900 hover:text-white'} transition-colors" style="padding-left:${8+Math.min(x.path.split('/').length,8)*10}px"><i class="ph ${x.type==='directory'?'ph-folder':'ph-file'} mr-2"></i>${esc(x.name)}</button>`).join('');
    document.querySelectorAll('[data-file]').forEach(b=>b.onclick=()=>openFile(b.dataset.file));
    updateContext(items.filter(item=>item.type!=='directory').length);
  }catch(e){toast(e.message,true)}
}

async function openFile(path){
  const data=(await api(`/api/workspaces/${state.workspaceId}/file?path=${encodeURIComponent(path)}`)).data;
  $('editor-path').textContent=path;
  $('file-editor').value=data.content;
  $('file-editor-wrap').classList.remove('hidden');
  $('file-editor-wrap').classList.add('flex');
}

async function saveFile(){
  try{
    await api(`/api/workspaces/${state.workspaceId}/file`,{method:'PUT',body:JSON.stringify({path:$('editor-path').textContent,content:$('file-editor').value})});
    toast('Arquivo salvo');
    await loadTree();
  }catch(e){toast(e.message,true)}
}

async function runTerminal(command,approved=false){
  if(!state.workspaceId)return toast('Crie ou selecione um projeto',true);
  const out=$('terminal-output');
  out.innerHTML+=`<div class="text-violet-400 mt-2">$ ${esc(command)}</div>`;

  try{
    const {data,status}=await api(`/api/workspaces/${state.workspaceId}/shell`,{method:'POST',body:JSON.stringify({command,approved})});
    if(status===202){
      state.approvalId=data.approval_id;
      $('approval-command').textContent=data.command;
      modal('approval-modal');
      return;
    }
    out.innerHTML+=`<pre class="whitespace-pre-wrap">${esc(data.stdout||'')}${data.stderr?`\n${esc(data.stderr)}`:''}\n[exit ${data.exit_code}] ${data.duration_ms}ms</pre>`;
    out.scrollTop=out.scrollHeight;
  }catch(e){
    out.innerHTML+=`<div class="text-red-400">${esc(e.message)}</div>`;
  }
}

async function refreshGitStatus(){
  if(!state.workspaceId)return toast('Crie ou selecione um projeto',true);
  const button=$('git-status');
  button.disabled=true;
  button.textContent='Atualizando...';
  try{
    const {data,status}=await api(`/api/workspaces/${state.workspaceId}/shell`,{method:'POST',body:JSON.stringify({command:'git status --short'})});
    if(status===202)throw new Error('O status do Git não deveria exigir aprovação');
    const output=[data.stdout,data.stderr].filter(Boolean).join('\n').trim();
    $('git-output').textContent=output||'Workspace limpo. Nenhuma alteração pendente.';
  }catch(error){
    $('git-output').textContent=error.message;
  }finally{
    button.disabled=false;
    button.textContent='Atualizar';
  }
}

async function resolveApproval(approve){
  try{
    const data=(await api(`/api/approvals/${state.approvalId}`,{method:'POST',body:JSON.stringify({approve})})).data;
    modal('approval-modal',false);
    if(data.result){
      const r=data.result;
      $('terminal-output').innerHTML+=`<pre>${esc(r.stdout||'')}${esc(r.stderr||'')}\n[exit ${r.exit_code}]</pre>`;
    }
    toast(approve?'Comando executado':'Comando recusado');
  }catch(e){toast(e.message,true)}
}

async function createProject(e){
  e.preventDefault();
  try{
    const w=(await api('/api/workspaces',{method:'POST',body:JSON.stringify({name:$('project-name').value||'Novo projeto'})})).data;
    if($('project-url').value.trim())await api(`/api/workspaces/${w.id}/clone`,{method:'POST',body:JSON.stringify({url:$('project-url').value.trim(),branch:$('project-branch').value.trim()})});
    modal('project-modal',false);
    await loadWorkspaces();
    await selectWorkspace(w.id);
    toast('Projeto criado');
  }catch(err){toast(err.message,true)}
}

async function uploadFiles(files){
  if(!state.workspaceId)return toast('Selecione um projeto',true);
  const form=new FormData();
  [...files].forEach(f=>form.append('files',f));
  try{
    await api(`/api/workspaces/${state.workspaceId}/upload`,{method:'POST',body:form});
    toast('Arquivos enviados');
    await loadTree();
  }catch(e){toast(e.message,true)}
}

function switchTab(name){
  state.rightTab=name;
  document.querySelectorAll('.tab-pane').forEach(p=>{
    p.classList.add('hidden');
    p.classList.remove('flex');
  });
  const pane=$(`tab-${name}`);
  if(pane){
    pane.classList.remove('hidden');
    pane.classList.add('flex');
  }
  document.querySelectorAll('.tab').forEach(b=>{
    if(b.dataset.tab===name){
      b.classList.add('text-white');
      b.classList.remove('text-zinc-400');
      b.classList.add('border-violet-500');
      b.classList.remove('border-transparent');
    }else{
      b.classList.remove('text-white');
      b.classList.add('text-zinc-400');
      b.classList.remove('border-violet-500');
      b.classList.add('border-transparent');
    }
  });
}

// Auth form
$('auth-form').onsubmit=async e=>{
  e.preventDefault();
  $('auth-error').textContent='';
  try{
    const path=state.authMode==='login'?'/api/auth/login':'/api/auth/register';
    await api(path,{method:'POST',body:JSON.stringify({username:$('auth-username').value,password:$('auth-password').value})});
    location.reload();
  }catch(err){$('auth-error').textContent=err.message}
};

$('login-tab').onclick=()=>{
  state.authMode='login';
  $('login-tab').className='rounded-lg py-2 text-sm bg-zinc-800 font-medium transition-colors';
  $('register-tab').className='rounded-lg py-2 text-sm text-zinc-400 transition-colors';
};

$('register-tab').onclick=()=>{
  state.authMode='register';
  $('register-tab').className='rounded-lg py-2 text-sm bg-zinc-800 font-medium transition-colors';
  $('login-tab').className='rounded-lg py-2 text-sm text-zinc-400 transition-colors';
};

// Chat
$('send-btn').onclick=send;
$('composer').onkeydown=e=>{if((e.ctrlKey||e.metaKey)&&e.key==='Enter')send()};
$('composer').oninput=resizeComposer;
$('new-chat-btn').onclick=createSession;
$('new-project-btn').onclick=()=>modal('project-modal');
$('agent-btn').onclick=()=>{setMode('agent',true);$('composer').focus();toast('Modo Agente ativado')};
document.querySelectorAll('[data-mode]').forEach(button=>button.onclick=()=>setMode(button.dataset.mode,true));

// Project form
$('project-form').onsubmit=createProject;

// Settings
$('settings-btn').onclick=async()=>{
  const c=(await api('/api/config')).data;
  $('provider-input').value=c.provider||'';
  $('model-input').value=c.model||'';
  $('base-url-input').value=c.base_url||'';
  modal('settings-modal');
};

$('settings-form').onsubmit=async e=>{
  e.preventDefault();
  try{
    await api('/api/config',{method:'POST',body:JSON.stringify({provider:$('provider-input').value,model:$('model-input').value,base_url:$('base-url-input').value,...($('api-key-input').value?{api_key:$('api-key-input').value}:{})})});
    toast('Configuração salva');
    if($('github-token-input').value){
      await api('/api/integrations/github',{method:'POST',body:JSON.stringify({token:$('github-token-input').value})});
    }
    modal('settings-modal',false);
    location.reload();
  }catch(err){toast(err.message,true)}
};

$('logout-btn').onclick=async()=>{
  await api('/api/auth/logout',{method:'POST',body:'{}'});
  location.reload();
};

// Modals
document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>modal(b.dataset.close,false));

// File upload
$('upload-btn').onclick=()=>$('file-input').click();
$('file-input').onchange=e=>uploadFiles(e.target.files);
$('repo-btn').onclick=()=>modal('project-modal');

// File editor
$('save-file').onclick=saveFile;
$('refresh-tree').onclick=loadTree;
$('file-search').oninput=loadTree;

// Terminal
$('terminal-run').onclick=()=>{
  const c=$('terminal-input').value.trim();
  if(c){$('terminal-input').value='';runTerminal(c)}
};
$('terminal-input').onkeydown=e=>{if(e.key==='Enter')$('terminal-run').click()};
$('terminal-focus').onclick=()=>{
  setRightPanel(true);
  switchTab('terminal');
  setTimeout(()=>$('terminal-input').focus(),100);
};

// Git
$('git-status').onclick=refreshGitStatus;

// Approval
$('approval-accept').onclick=()=>resolveApproval(true);
$('approval-reject').onclick=()=>resolveApproval(false);

// Tabs
document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>switchTab(b.dataset.tab));

// Mobile sidebar
$('open-left').onclick=()=>setLeftPanel(true);
$('close-left').onclick=()=>setLeftPanel(false);
$('mobile-backdrop').onclick=()=>setLeftPanel(false);

// Model picker
$('model-trigger').onclick=()=>toggleModelMenu();
$('model-trigger').onkeydown=event=>{
  if(event.key==='ArrowDown'||event.key==='Enter'||event.key===' '){
    event.preventDefault();
    toggleModelMenu(true);
  }
};
$('model-menu').onkeydown=event=>{
  if(event.key==='ArrowDown'){event.preventDefault();moveModelFocus(1)}
  if(event.key==='ArrowUp'){event.preventDefault();moveModelFocus(-1)}
  if(event.key==='Home'){event.preventDefault();document.querySelector('[data-model-id]')?.focus()}
  if(event.key==='End'){
    event.preventDefault();
    const options=document.querySelectorAll('[data-model-id]');
    options[options.length-1]?.focus();
  }
  if(event.key==='Enter'&&document.activeElement?.dataset.modelId){
    event.preventDefault();
    selectModel(document.activeElement.dataset.modelId);
    $('model-trigger').focus();
  }
};
document.addEventListener('click',event=>{
  if(!$('model-picker').contains(event.target))toggleModelMenu(false);
});

// Toggle right panel
$('toggle-right').onclick=()=>{
  setRightPanel(!state.rightOpen);
};
$('close-right').onclick=()=>setRightPanel(false);

document.addEventListener('keydown',event=>{
  if(event.key!=='Escape')return;
  if(!$('model-menu').classList.contains('hidden')){
    toggleModelMenu(false);
    $('model-trigger').focus();
    return;
  }
  document.querySelectorAll('.modal-backdrop.flex').forEach(element=>modal(element.id,false));
  if(window.innerWidth<768)setLeftPanel(false);
  if(window.innerWidth<1024)setRightPanel(false);
});

document.querySelectorAll('.modal-backdrop').forEach(element=>{
  element.addEventListener('click',event=>{if(event.target===element)modal(element.id,false)});
});

window.matchMedia('(min-width: 1024px)').addEventListener('change',event=>setRightPanel(event.matches));

// Initialize
resizeComposer();
init();
