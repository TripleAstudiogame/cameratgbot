let organizations=[], healthData={}, token=localStorage.getItem('nvr_token'), role=localStorage.getItem('nvr_role'), currentFilter='all', searchQuery='', currentUserFilter=null;
function esc(s){if(!s)return'';const d=document.createElement('div');d.appendChild(document.createTextNode(s));return d.innerHTML;}

if(token && !role) {
    try {
        const p = JSON.parse(atob(token.split('.')[1]));
        role = p.role || (p.sub === 'Admin' ? 'admin' : 'user');
        localStorage.setItem('nvr_role', role);
        if(p.id) localStorage.setItem('nvr_user_id', p.id);
    } catch(e) {}
}

document.addEventListener('DOMContentLoaded',()=>{
    document.getElementById('logoutBtn')?.addEventListener('click',e=>{e.preventDefault();logout();});
    document.addEventListener('click',e=>{if(!document.getElementById('notifWrapper')?.contains(e.target))document.getElementById('notifDropdown')?.classList.remove('show');});
    token?showDashboard():showLogin();
});
function showLogin(){document.getElementById('loginScreen').style.display='flex';document.getElementById('appContainer').style.display='none';}
function showDashboard(){
    document.getElementById('loginScreen').style.display='none';
    document.getElementById('appContainer').style.display='flex';
    
    if (token) {
        try {
            const payload = JSON.parse(atob(token.split('.')[1]));
            role = payload.role;
            localStorage.setItem('nvr_role', role);
            localStorage.setItem('nvr_user_id', payload.id);
            
            // Update UI with real username
            const nameEl = document.querySelector('.user-name');
            const avatarEl = document.querySelector('.avatar');
            if (nameEl) nameEl.innerText = payload.sub || 'User';
            if (avatarEl) avatarEl.innerText = (payload.sub || 'U').charAt(0).toUpperCase();
        } catch(e) {}
    }

    if(role==='admin'){
        document.getElementById('navUsers').style.display='block';
        document.getElementById('btnExportMine').style.display='inline-flex';
        document.getElementById('btnExportAll').style.display='inline-flex';
        document.getElementById('btnExportUser').style.display='none';
    }else{
        document.getElementById('navUsers').style.display='none';
        document.getElementById('btnExportMine').style.display='none';
        document.getElementById('btnExportAll').style.display='none';
        document.getElementById('btnExportUser').style.display='inline-flex';
    }
    fetchAll();
    checkUpdateStatus();
    setInterval(checkUpdateStatus, 30000);
}

// Auth
async function handleLogin(e){
    e.preventDefault();const el=document.getElementById('loginError');el.style.display='none';
    const fd=new FormData();fd.append('username',document.getElementById('username').value);fd.append('password',document.getElementById('password').value);
    try{
        const r=await fetch('/api/login',{method:'POST',body:fd});
        if(r.ok){
            const d=await r.json();
            token=d.access_token;
            role=d.role;
            localStorage.setItem('nvr_token',token);
            localStorage.setItem('nvr_role',role);
            try {
                const payload = JSON.parse(atob(token.split('.')[1]));
                localStorage.setItem('nvr_user_id', payload.id);
            } catch(e) {}
            showDashboard();
        }
        else el.style.display='block';
    }catch(err){el.style.display='block';}
}
function logout(){
    token=null;role=null;
    localStorage.removeItem('nvr_token');
    localStorage.removeItem('nvr_role');
    localStorage.removeItem('nvr_user_id');
    location.reload();
}
async function api(url,opts={}){if(!opts.headers)opts.headers={};if(token)opts.headers['Authorization']=`Bearer ${token}`;const r=await fetch(url,opts);if(r.status===401){logout();throw Error('401');}return r;}

// Data
async function fetchAll(){
    try{
        const[orgR,hR]=await Promise.all([api('/api/organizations'),api('/api/health')]);
        organizations=await orgR.json();healthData=await hR.json();
        updateStats();updateNotif();renderGrid();
    }catch(e){console.error(e);}
}

async function checkUpdateStatus() {
    try {
        const r = await api('/api/system/update-status');
        if (r.ok) {
            const data = await r.json();
            const textEl = document.getElementById('updateText');
            const dotEl = document.getElementById('updateDot');
            if (textEl && dotEl) {
                textEl.innerText = data.status || 'Нет данных';
                textEl.title = data.status || '';
                if (data.status && data.status.includes('ОШИБКА')) {
                    dotEl.style.background = '#EF4444';
                    dotEl.style.boxShadow = '0 0 8px #EF4444';
                } else if (data.status && data.status.includes('CHECK:')) {
                    dotEl.style.background = '#10B981';
                    dotEl.style.boxShadow = '0 0 8px #10B981';
                } else {
                    dotEl.style.background = '#3B82F6';
                    dotEl.style.boxShadow = '0 0 8px #3B82F6';
                }
            }
        }
    } catch(e) {}
}

// Pages
function switchPage(page,btn){
    document.querySelectorAll('.page').forEach(p=>p.classList.remove('active-page'));
    document.getElementById('page-'+page).classList.add('active-page');
    document.querySelectorAll('.nav-menu a').forEach(a=>a.classList.remove('active'));
    btn.classList.add('active');
    
    // Clear user filter when leaving dashboard
    if(page !== 'main') currentUserFilter = null;
    if(page === 'main') renderGrid(); // Re-render to clear user filter
    if(page==='users') loadUsers();
    if(page==='analytics')loadAnalytics();
    if(page==='settings')loadSettings();
}

// Stats
function updateStats(){
    const now=new Date(),in30=new Date(now.getTime()+30*864e5);
    let act=0,exp=0,subs=0;
    const list = getFiltered();
    list.forEach(o=>{if(o.is_active)act++;subs+=(o.subscribers?.length||0);try{const d=new Date(o.subscription_end_date);if(d<=in30&&d>now)exp++;}catch{}});
    document.getElementById('statTotal').textContent=list.length;
    document.getElementById('statActive').textContent=act;
    document.getElementById('statExpiring').textContent=exp;
    document.getElementById('statSubscribers').textContent=subs;
}

// Notif
function updateNotif(){
    const now=new Date(),in30=new Date(now.getTime()+30*864e5),items=[];
    const list = getFiltered();
    list.forEach(o=>{try{const d=new Date(o.subscription_end_date);if(d<=now)items.push({t:'danger',i:'alert-circle',m:`${o.name} — подписка истекла!`});else if(d<=in30){const days=Math.ceil((d-now)/864e5);items.push({t:'warn',i:'warning',m:`${o.name} — через ${days} дн.`});}}catch{}});
    const badge=document.getElementById('notifBadge'),listEl=document.getElementById('notifList');
    if(items.length){badge.textContent=items.length;badge.style.display='flex';listEl.innerHTML=items.map(i=>`<div class="notif-item ${i.t}"><ion-icon name="${i.i}-outline"></ion-icon><span>${esc(i.m)}</span></div>`).join('');}
    else{badge.style.display='none';listEl.innerHTML='<p class="notif-empty">Нет уведомлений</p>';}
}
function toggleNotif(){document.getElementById('notifDropdown').classList.toggle('show');}

// Search & Filter
function handleSearch(){searchQuery=document.getElementById('searchInput').value.toLowerCase();renderGrid();}
function setFilter(f,btn){currentFilter=f;currentUserFilter=null;document.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active'));btn.classList.add('active');renderGrid();}
function getFiltered(){
    const now=new Date(),in30=new Date(now.getTime()+30*864e5);
    const myUserId = parseInt(localStorage.getItem('nvr_user_id'));
    return organizations.filter(o=>{
        if(currentUserFilter !== null) {
            if (o.user_id !== currentUserFilter) return false;
        } else {
            if (o.user_id !== myUserId) return false;
        }
        if(searchQuery&&!o.name.toLowerCase().includes(searchQuery)&&!o.mail_username.toLowerCase().includes(searchQuery))return false;
        if(currentFilter==='active')return o.is_active;if(currentFilter==='inactive')return!o.is_active;
        if(currentFilter==='expiring'){try{const d=new Date(o.subscription_end_date);return d<=in30&&d>now;}catch{return false;}}return true;
    });
}

// Render
function renderGrid(){
    const grid=document.getElementById('orgGrid'),list=getFiltered();
    if(!list.length){grid.innerHTML=`<div class="empty-state"><ion-icon name="folder-open-outline"></ion-icon><p>${organizations.length?'Ничего не найдено':'Нет организаций'}</p></div>`;return;}
    grid.innerHTML='';const now=new Date(),in30=new Date(now.getTime()+30*864e5);
    list.forEach(org=>{
        let endDate='—',isExp=false,isExpiring=false;
        try{const d=new Date(org.subscription_end_date);if(!isNaN(d)){endDate=d.toLocaleDateString('ru-RU');if(d<=now)isExp=true;else if(d<=in30)isExpiring=true;}}catch{}
        let sc=org.is_active?'status-active':'status-inactive',st=org.is_active?'Активен':'Остановлен';
        if(isExpiring&&org.is_active){sc='status-expiring';st='Истекает';}if(isExp){sc='status-inactive';st='Просрочен';}

        // Health
        const h=healthData[org.id]||{};
        const imapDot=h.imap_ok?'dot-green':(h.last_check?'dot-red':'dot-gray');
        const botDot=h.bot_ok?'dot-green':(h.last_check?'dot-red':'dot-gray');
        let lastCheck='—';
        if(h.last_check){try{const d=new Date(h.last_check);lastCheck=d.toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit',second:'2-digit'});}catch{}}

        let contact='';
        if(org.contact_name||org.contact_phone||org.contact_title)contact=`<div class="contact-block"><ion-icon name="person-circle-outline" style="font-size:18px;color:var(--muted);margin-top:2px"></ion-icon><div class="contact-details"><span class="contact-name">${esc(org.contact_name)}</span><span class="contact-title-text">${esc(org.contact_title)}</span><span class="contact-phone">${esc(org.contact_phone)}</span></div></div>`;

        const extendBtn = role === 'admin' ? `<button class="btn-icon btn-success-action flex-1" onclick="openRenewModal(${org.id})"><ion-icon name="cash-outline"></ion-icon> Продлить</button>` : '';

        const c=document.createElement('div');c.className='org-card'+(org.is_active?'':' card-inactive');
        c.innerHTML=`
<div class="org-header"><div class="org-title">${esc(org.name)}</div><div class="status-badge ${sc}"><div class="status-dot"></div>${st}</div></div>
<div class="health-row"><div class="health-dot"><span class="dot ${imapDot}"></span>Почта</div><div class="health-dot"><span class="dot ${botDot}"></span>Бот</div><div class="health-dot" style="margin-left:auto;font-size:10px;">⏱ ${lastCheck}</div></div>
<div class="org-info">
<div class="info-row"><ion-icon name="mail-outline"></ion-icon><span class="val">${esc(org.mail_username)}</span></div>
<div class="info-row"><ion-icon name="people-outline"></ion-icon><span>Подписчиков: <span class="subs-link" onclick="openSubsModal(${org.id})">${org.subscribers?.length||0}</span></span></div>
<div class="info-row"><ion-icon name="calendar-outline"></ion-icon><span>До: <span class="val">${endDate}</span></span></div>
<div class="info-row"><ion-icon name="timer-outline"></ion-icon><span>Чек: <span class="val">${org.mail_check_interval > 0 ? org.mail_check_interval+'с' : 'глоб.'}</span> / TG: <span class="val">${org.telegram_cooldown > 0 ? org.telegram_cooldown+'с' : 'глоб.'}</span></span></div>
${contact}
</div>
<div style="margin-bottom:10px;"><span class="events-link" onclick="openEventsModal(${org.id})">📋 Лента событий</span></div>
<div class="org-actions">
${extendBtn}
<button class="btn-icon btn-info" onclick="testConn(${org.id})" title="Тест"><ion-icon name="flask-outline"></ion-icon></button>
<button class="btn-icon" onclick="toggleOrg(${org.id})" title="${org.is_active?'Стоп':'Старт'}"><ion-icon name="${org.is_active?'pause-outline':'play-outline'}"></ion-icon></button>
<button class="btn-icon" onclick="openModal('edit',${org.id})"><ion-icon name="create-outline"></ion-icon></button>
<button class="btn-icon btn-danger" onclick="deleteOrg(${org.id})"><ion-icon name="trash-outline"></ion-icon></button>
</div>`;
        grid.appendChild(c);
    });
}

// Actions
function openRenewModal(id){
    document.getElementById('renewOrgId').value = id;
    document.getElementById('renewModal').classList.add('active');
}
function closeRenewModal(){
    document.getElementById('renewModal').classList.remove('active');
}
async function submitRenew(days){
    const id = document.getElementById('renewOrgId').value;
    try{
        await api(`/api/organizations/${id}/extend_subscription`,{method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({days})});
        fetchAll();
        closeRenewModal();
    }catch{alert('Ошибка');}
}
async function toggleOrg(id){
    // Мгновенный визуальный отклик (optimistic UI)
    const org=organizations.find(o=>o.id===id);
    if(org){org.is_active=!org.is_active;renderGrid();}
    try{
        await api(`/api/organizations/${id}/toggle`,{method:'PATCH'});
        await fetchAll();
        // Движку нужно ~3 сек чтобы обновить health — подтягиваем повторно
        setTimeout(async()=>{try{const hR=await api('/api/health');healthData=await hR.json();renderGrid();}catch{}},3500);
    }catch{alert('Ошибка');fetchAll();}
}
async function deleteOrg(id){if(!confirm('Удалить безвозвратно?'))return;try{await api(`/api/organizations/${id}`,{method:'DELETE'});fetchAll();}catch{alert('Ошибка');}}

// Test Connection
async function testConn(id){
    document.getElementById('testResult').innerHTML='<div class="test-loading">⏳ Проверяю соединение...</div>';
    document.getElementById('testModal').classList.add('active');
    try{
        const r=await api(`/api/organizations/${id}/test`,{method:'POST'});const d=await r.json();
        document.getElementById('testResult').innerHTML=`
<div class="test-row"><ion-icon name="${d.imap_ok?'checkmark-circle':'close-circle'}" class="${d.imap_ok?'test-ok':'test-fail'}"></ion-icon><span>IMAP (Mail.ru): ${d.imap_ok?'✅ Подключение успешно':'❌ '+esc(d.imap_error)}</span></div>
<div class="test-row"><ion-icon name="${d.bot_ok?'checkmark-circle':'close-circle'}" class="${d.bot_ok?'test-ok':'test-fail'}"></ion-icon><span>Telegram Бот: ${d.bot_ok?'✅ '+esc(d.bot_name||'Работает'):'❌ '+esc(d.bot_error)}</span></div>`;
    }catch{document.getElementById('testResult').innerHTML='<div class="test-fail">Ошибка запроса</div>';}
}
function closeTestModal(){document.getElementById('testModal').classList.remove('active');}

// Events Modal
async function openEventsModal(id){
    const org=organizations.find(o=>o.id===id);
    document.getElementById('eventsTitle').textContent=`События — ${org?.name||''}`;
    document.getElementById('eventsList').innerHTML='<p class="notif-empty">Загрузка...</p>';
    document.getElementById('eventsModal').classList.add('active');
    try{
        const r=await api(`/api/events/${id}`);const events=await r.json();
        if(!events.length){document.getElementById('eventsList').innerHTML='<p class="notif-empty">Нет событий</p>';return;}
        const icons={notification:'📹',error:'❌',subscriber:'👤',system:'⚙️'};
        const cls={notification:'notif',error:'err',subscriber:'sub',system:'sys'};
        document.getElementById('eventsList').innerHTML=events.map(e=>{
            const t=new Date(e.created_at);const ts=t.toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit'});
            const dt=t.toLocaleDateString('ru-RU',{day:'2-digit',month:'2-digit'});
            return`<div class="event-item"><span class="event-time">${dt} ${ts}</span><span class="event-icon ${cls[e.event_type]||'sys'}">${icons[e.event_type]||'📌'}</span><span class="event-msg">${esc(e.message)}</span></div>`;
        }).join('');
    }catch{document.getElementById('eventsList').innerHTML='<p class="notif-empty">Ошибка загрузки</p>';}
}
function closeEventsModal(){document.getElementById('eventsModal').classList.remove('active');}

// Subscribers Modal
function openSubsModal(id){
    const org=organizations.find(o=>o.id===id);if(!org)return;
    document.getElementById('subsModalTitle').textContent=`Подписчики — ${org.name}`;
    const list=document.getElementById('subsList');
    if(!org.subscribers?.length){list.innerHTML='<p class="notif-empty">Нет подписчиков</p>';}
    else list.innerHTML=org.subscribers.map(s=>`<div class="sub-item"><span class="sub-id">${s}</span><button class="sub-remove" onclick="removeSub(${id},${s})"><ion-icon name="close-outline"></ion-icon> Удалить</button></div>`).join('');
    document.getElementById('subsModal').classList.add('active');
}
function closeSubsModal(){document.getElementById('subsModal').classList.remove('active');}
async function removeSub(oid,cid){if(!confirm(`Удалить ${cid}?`))return;try{await api(`/api/organizations/${oid}/subscribers/${cid}`,{method:'DELETE'});fetchAll();closeSubsModal();}catch{alert('Ошибка');}}

// Org Modal
function switchModalTab(tab){
    document.querySelectorAll('.modal-tab').forEach(b=>b.classList.remove('active'));
    document.querySelectorAll('.modal-tab-content').forEach(c=>c.classList.remove('active'));
    
    const btnId = tab==='main'?'tabBtnMain':(tab==='settings'?'tabBtnSettings':(tab==='access'?'tabBtnAccess':'tabBtnCameras'));
    const contentId = tab==='main'?'modalTabMain':(tab==='settings'?'modalTabSettings':(tab==='access'?'modalTabAccess':'modalTabCameras'));
    
    document.getElementById(btnId).classList.add('active');
    document.getElementById(contentId).classList.add('active');
    
    if(tab==='access') fetchAccessData();
}

function switchAccessSub(sub){
    document.querySelectorAll('.access-sub-tab').forEach(b=>b.classList.remove('active'));
    document.getElementById(sub==='approved'?'accessSubApproved':'accessSubPending').classList.add('active');
    document.getElementById('accessApprovedList').style.display = sub==='approved'?'flex':'none';
    document.getElementById('accessPendingList').style.display = sub==='pending'?'flex':'none';
}

async function fetchAccessData(){
    const oid = document.getElementById('orgId').value;
    if(!oid) return;
    
    try {
        const [appRes, pendRes] = await Promise.all([
            api(`/api/organizations/${oid}/access?status=approved`),
            api(`/api/organizations/${oid}/access?status=pending`)
        ]);
        
        const approved = await appRes.json();
        const pending = await pendRes.json();
        
        const badge = document.getElementById('pendingBadge');
        if(pending.length > 0){
            badge.textContent = pending.length;
            badge.style.display = 'inline-flex';
        } else {
            badge.style.display = 'none';
        }
        
        renderAccessList('accessApprovedList', approved, true);
        renderAccessList('accessPendingList', pending, false);
    } catch(e) { console.error(e); }
}

function renderAccessList(containerId, users, isApproved){
    const container = document.getElementById(containerId);
    if(users.length === 0){
        container.innerHTML = `<div class="access-empty">${isApproved ? 'Нет одобренных пользователей' : 'Нет новых заявок'}</div>`;
        return;
    }
    
    container.innerHTML = users.map(u => `
        <div class="access-card">
            <div class="access-avatar">${u.first_name?u.first_name[0].toUpperCase():'U'}</div>
            <div class="access-info">
                <div class="access-name">${u.first_name||''} ${u.last_name||''}</div>
                <div class="access-phone">${u.phone||'Нет номера'}</div>
                <div class="access-id">ID: ${u.chat_id}</div>
            </div>
            <div class="access-actions">
                ${isApproved ? 
                    `<button type="button" class="btn-reject btn-revoke" onclick="revokeAccess(${u.id})" title="Отозвать доступ"><ion-icon name="trash-outline"></ion-icon></button>` :
                    `<button type="button" class="btn-approve" onclick="approveRequest(${u.id})" title="Одобрить"><ion-icon name="checkmark-outline"></ion-icon></button>
                     <button type="button" class="btn-reject" onclick="rejectRequest(${u.id})" title="Отклонить"><ion-icon name="close-outline"></ion-icon></button>`
                }
            </div>
        </div>
    `).join('');
}

async function approveRequest(rid){
    const oid = document.getElementById('orgId').value;
    try {
        await api(`/api/organizations/${oid}/access/${rid}/approve`, {method:'POST'});
        fetchAccessData();
        fetchAll();
    } catch(e){ alert('Ошибка при одобрении'); }
}

async function rejectRequest(rid){
    const oid = document.getElementById('orgId').value;
    if(!confirm('Отклонить заявку?')) return;
    try {
        await api(`/api/organizations/${oid}/access/${rid}/reject`, {method:'POST'});
        fetchAccessData();
    } catch(e){ alert('Ошибка при отклонении'); }
}

async function revokeAccess(rid){
    const oid = document.getElementById('orgId').value;
    if(!confirm('Отозвать доступ у пользователя?')) return;
    try {
        await api(`/api/organizations/${oid}/access/${rid}`, {method:'DELETE'});
        fetchAccessData();
        fetchAll();
    } catch(e){ alert('Ошибка при отзыве доступа'); }
}
function openModal(mode,id=null){
    document.getElementById('statusGroup').style.display=mode==='edit'?'flex':'none';
    document.getElementById('tabBtnAccess').style.display=mode==='edit'?'block':'none';
    document.getElementById('tabBtnCameras').style.display=mode==='edit'?'block':'none';
    switchModalTab('main');
    switchAccessSub('approved');
    
    if(mode==='add'){document.getElementById('modalTitle').textContent='Новая организация';document.getElementById('orgForm').reset();document.getElementById('orgId').value='';document.getElementById('orgNotes').value='';document.getElementById('orgMailInterval').value='0';document.getElementById('orgTgCooldown').value='0';document.getElementById('cameraInputs').innerHTML='';}
    else{document.getElementById('modalTitle').textContent='Редактировать';const o=organizations.find(x=>x.id===id);if(o){document.getElementById('orgId').value=o.id;document.getElementById('orgName').value=o.name;document.getElementById('orgToken').value=o.bot_token;document.getElementById('orgMail').value=o.mail_username;document.getElementById('orgPass').value=o.mail_password;document.getElementById('orgActive').checked=o.is_active;document.getElementById('contactName').value=o.contact_name||'';document.getElementById('contactPhone').value=o.contact_phone||'';document.getElementById('contactTitle').value=o.contact_title||'';document.getElementById('orgNotes').value=o.notes||'';document.getElementById('orgMailInterval').value=String(o.mail_check_interval||0);document.getElementById('orgTgCooldown').value=String(o.telegram_cooldown||0);
    const cameras = typeof o.cameras === 'string' ? JSON.parse(o.cameras || '{}') : (o.cameras || {});
    const camContainer = document.getElementById('cameraInputs');
    if(Object.keys(cameras).length === 0){ camContainer.innerHTML = '<p class="notif-empty">Камеры пока не обнаружены</p>'; }
    else { 
        const camHTML = Object.keys(cameras).map(code => `
            <div class="camera-card">
                <div class="camera-icon">
                    <ion-icon name="videocam-outline"></ion-icon>
                </div>
                <div class="camera-info">
                    <div class="camera-header">
                        <span class="camera-label">Код камеры:</span>
                        <span class="camera-badge">${code}</span>
                    </div>
                    <input type="text" class="camera-name-input" data-code="${code}" value="${esc(cameras[code]||'')}" placeholder="Название (например: Главный вход, Улица...)">
                </div>
            </div>
        `).join('');
        camContainer.innerHTML = `<div class="camera-list">${camHTML}</div>`;
    }
    }}
    document.getElementById('orgModal').classList.add('active');
}
function closeModal(){document.getElementById('orgModal').classList.remove('active');}
async function handleFormSubmit(e){
    e.preventDefault();
    const submitBtn = e.target.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;
    submitBtn.innerHTML = '<ion-icon name="hourglass-outline"></ion-icon> Сохранение...';
    submitBtn.disabled = true;
    
    const id=document.getElementById('orgId').value;const isEdit=id!=='';
    const cameras = {};
    document.querySelectorAll('.camera-name-input').forEach(i => cameras[i.dataset.code] = i.value.trim());
    const data={name:document.getElementById('orgName').value,bot_token:document.getElementById('orgToken').value,mail_username:document.getElementById('orgMail').value,mail_password:document.getElementById('orgPass').value,is_active:document.getElementById('orgActive').checked,contact_name:document.getElementById('contactName').value,contact_phone:document.getElementById('contactPhone').value,contact_title:document.getElementById('contactTitle').value,notes:document.getElementById('orgNotes').value,mail_check_interval:document.getElementById('orgMailInterval').value||0,telegram_cooldown:document.getElementById('orgTgCooldown').value||0,cameras:cameras};
    
    try{
        const r=await api(isEdit?`/api/organizations/${id}`:'/api/organizations',{method:isEdit?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
        if(r.ok){
            closeModal();
            await fetchAll();
            setTimeout(async()=>{try{const hR=await api('/api/health');healthData=await hR.json();renderGrid();}catch{}},3500);
        }else{
            const e=await r.json();alert(e.detail||'Ошибка');
        }
    }catch{
        alert('Ошибка соединения');
    }finally{
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
    }
}

// Users Page
let usersData = [];
async function loadUsers(){
    try{
        const r=await api('/api/users');
        if(!r.ok) return;
        usersData = await r.json();
        renderUsers();
    }catch(e){console.error(e);}
}

function renderUsers(){
    const grid = document.getElementById('userGrid');
    if(!usersData.length){
        grid.innerHTML = '<div class="empty-state"><ion-icon name="people-outline"></ion-icon><p>Нет пользователей</p></div>';
        return;
    }
    grid.innerHTML = usersData.map(u => {
        const orgsCount = organizations.filter(o => o.user_id === u.id).length;
        return `
            <div class="org-card" style="cursor:pointer;" onclick="showUserOrgs(${u.id})">
                <div class="org-header">
                    <div class="org-title">${esc(u.name || u.username)}</div>
                </div>
                <div class="org-info">
                    <div class="info-row"><ion-icon name="person-outline"></ion-icon><span>Логин: <span class="val">${esc(u.username)}</span></span></div>
                    <div class="info-row"><ion-icon name="call-outline"></ion-icon><span>Телефон: <span class="val">${esc(u.phone)}</span></span></div>
                    <div class="info-row"><ion-icon name="folder-open-outline"></ion-icon><span>Организаций: <span class="val">${orgsCount}</span></span></div>
                </div>
                <div class="org-actions" style="margin-top:15px;" onclick="event.stopPropagation()">
                    <button class="btn-icon btn-success-action flex-1" onclick="showUserOrgs(${u.id})"><ion-icon name="eye-outline"></ion-icon> Показать организации</button>
                    <button class="btn-icon btn-danger" onclick="deleteUser(${u.id})"><ion-icon name="trash-outline"></ion-icon></button>
                </div>
            </div>
        `;
    }).join('');
}

function showUserOrgs(id){
    currentUserFilter = id;
    document.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active'));
    document.querySelector('.filter-btn').classList.add('active'); // set "All" visual
    switchPage('main', document.querySelector('.nav-menu a[data-page="main"]'));
    renderGrid();
}

function openUserModal(){
    document.getElementById('userForm').reset();
    document.getElementById('userModal').classList.add('active');
}
function closeUserModal(){document.getElementById('userModal').classList.remove('active');}

async function handleUserSubmit(e){
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    btn.disabled = true;
    
    const data = {
        name: document.getElementById('newUserName').value,
        phone: document.getElementById('newUserPhone').value,
        username: document.getElementById('newUserLogin').value,
        password: document.getElementById('newUserPass').value
    };
    
    try {
        const r = await api('/api/users', {method: 'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(data)});
        if(r.ok) {
            closeUserModal();
            loadUsers();
        } else {
            const err = await r.json();
            alert(err.detail || 'Ошибка');
        }
    } catch (e) {
        console.error(e);
        alert('Ошибка соединения с сервером');
    } finally {
        btn.disabled = false;
    }
}

async function deleteUser(id){
    if(!confirm('Удалить пользователя? Его организации будут перенесены к администратору.')) return;
    try {
        await api(`/api/users/${id}`, {method:'DELETE'});
        loadUsers();
        fetchAll(); // Refresh organizations in background
    } catch { alert('Ошибка'); }
}

// Analytics
let dailyChart,cameraChart;
async function loadAnalytics(){
    try{
        const[dR,cR]=await Promise.all([api('/api/analytics/daily'),api('/api/analytics/cameras')]);
        const daily=await dR.json(),cameras=await cR.json();
        const ctx1=document.getElementById('dailyChart').getContext('2d');
        if(dailyChart)dailyChart.destroy();
        dailyChart=new Chart(ctx1,{type:'line',data:{labels:daily.map(d=>d.day?.slice(5)||''),datasets:[{label:'Уведомлений',data:daily.map(d=>d.count),borderColor:'#3B82F6',backgroundColor:'rgba(59,130,246,0.1)',fill:true,tension:.4}]},options:{responsive:true,plugins:{legend:{display:false}},scales:{x:{ticks:{color:'#71717A'},grid:{color:'#1F1F1F'}},y:{ticks:{color:'#71717A'},grid:{color:'#1F1F1F'}}}}});
        const ctx2=document.getElementById('cameraChart').getContext('2d');
        if(cameraChart)cameraChart.destroy();
        cameraChart=new Chart(ctx2,{type:'bar',data:{labels:cameras.map(c=>'📹 '+(c.message||'').replace('Камера ','')),datasets:[{label:'Срабатываний',data:cameras.map(c=>c.count),backgroundColor:'rgba(16,185,129,0.6)',borderRadius:4}]},options:{responsive:true,indexAxis:'y',plugins:{legend:{display:false}},scales:{x:{ticks:{color:'#71717A'},grid:{color:'#1F1F1F'}},y:{ticks:{color:'#71717A'},grid:{display:false}}}}});
    }catch(e){console.error(e);}
}

// Settings
async function loadSettings(){
    try{
        const r=await api('/api/settings');
        if(!r.ok) return;
        const s=await r.json();
        document.getElementById('setSubDays').value=s.default_subscription_days||'365';
    }catch{}
}
async function saveSettings(e){
    e.preventDefault();
    try{await api('/api/settings',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({default_subscription_days:document.getElementById('setSubDays').value})});alert('Настройки сохранены!');}catch{alert('Ошибка');}
}
async function changePassword(e){
    e.preventDefault();const msg=document.getElementById('passMsg');
    try{const r=await api('/api/settings/change-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({current_password:document.getElementById('curPass').value,new_password:document.getElementById('newPass').value})});
    if(r.ok){msg.className='msg-box ok';msg.textContent='✅ Пароль изменён';msg.style.display='block';document.getElementById('passwordForm').reset();}
    else{const d=await r.json();msg.className='msg-box err';msg.textContent='❌ '+(d.detail||'Ошибка');msg.style.display='block';}}
    catch{msg.className='msg-box err';msg.textContent='❌ Ошибка';msg.style.display='block';}
}

// Export
async function exportExcel(type = 'all'){
    try{
        let url = '/api/export';
        if (type === 'mine') {
            url += '?type=mine';
        } else if (currentUserFilter !== null) {
            url += '?user_id=' + currentUserFilter;
        }
        const r=await api(url);
        if(!r.ok) throw new Error(await r.text());
        const b=await r.blob();
        const a=document.createElement('a');
        a.href=URL.createObjectURL(b);
        a.download=`report_camera_${new Date().toISOString().slice(0,10)}.xlsx`;
        a.click();
    }catch(e){
        alert('Ошибка экспорта: ' + e.message);
    }
}

// Mobile
function toggleSidebar(){document.getElementById('sidebar').classList.toggle('open');}
