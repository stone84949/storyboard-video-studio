const state={
      project:{id:'storyboard-ultimate-001',title:'Storyboard Ultimate Workflow',aspect_ratio:'9:16',pipeline_target:'short-shorts',workflow_stage:'plan',px:58,task_id:'task-storyboard-001'},
      stages:['plan','approve','export','render','review','publish'],
      selectedMachineId:'beast',selectedSceneId:'scene-01',selectedJobId:'job-001',execute:false,
      projectNotes:'Review flagged assets before final render. Keep center safe for captions and leave room for logo or CTA.',
      machines:[{id:'beast',name:'BEAST',status:'online',engine:'hyperframes',jobs:1,note:'Primary render box'},{id:'cyberpower',name:'CyberPower',status:'idle',engine:'openmontage',jobs:0,note:'Control / handoff node'},{id:'skytech',name:'SkyTech',status:'idle',engine:'hyperframes',jobs:0,note:'Overflow worker'}],
      jobs:[{id:'job-001',label:'night-short-01',machineId:'beast',engine:'hyperframes',status:'running',progress:62},{id:'job-002',label:'review-handoff-01',machineId:'cyberpower',engine:'openmontage',status:'queued',progress:0}],
      checklist:[
        {id:'chk-1',label:'All scenes have images',done:false},
        {id:'chk-2',label:'No flagged shots remain',done:false},
        {id:'chk-3',label:'Caption-safe area checked',done:true},
        {id:'chk-4',label:'Project notes reviewed',done:true}
      ],
      events:[
        {time:'03:58',text:'Bridge write prepared for storyboard-ultimate-001.'},
        {time:'04:01',text:'BEAST reported 1 running job.'}
      ],
      validationResults:[],
      voiceoverNotes:'Narration should stay calm, paced, and documentary-style. Leave short breathing room between scenes.',
      voiceSettings:{wpm:132,buffer:0.3},
      scenes:[
        {id:'scene-01',title:'Cold open visual',assetUrl:'https://picsum.photos/seed/story-scene1/1080/1920',duration:3.2,start:0,transition:'fade',motionPreset:'zoom-in',status:'raw',assetState:'approved',captionMode:'center-title',notes:'Fast hook frame with dark center-safe composition.',narration:'This is where the story opens with a strong visual hook.',voStart:0.0,voEnd:2.9},
        {id:'scene-02',title:'Problem setup',assetUrl:'https://picsum.photos/seed/story-scene2/1080/1920',duration:4.8,start:3.2,transition:'cut',motionPreset:'pan-right-left',status:'approved',assetState:'approved',captionMode:'lower-third',notes:'Leave space on right side for captions.',narration:'Here we frame the problem and introduce the core tension.',voStart:3.3,voEnd:7.4},
        {id:'scene-03',title:'Main proof visual',assetUrl:'https://picsum.photos/seed/story-scene3/1080/1920',duration:5.1,start:8.0,transition:'fade',motionPreset:'pan-left-right',status:'approved',assetState:'approved',captionMode:'lower-third',notes:'Use as proof frame with product/service focus.',narration:'Now we move into the main proof point and visual evidence.',voStart:8.1,voEnd:12.4},
        {id:'scene-04',title:'CTA end frame',assetUrl:'https://picsum.photos/seed/story-scene4/1080/1920',duration:3.6,start:13.1,transition:'slide',motionPreset:'static',status:'approved',assetState:'approved',captionMode:'center-title',notes:'End card can accept final branded image swap.',narration:'Finish with the call to action and clear next step.',voStart:13.3,voEnd:16.2}
      ]
    };
    const q=id=>document.getElementById(id); const fmt=s=>`${Number(s).toFixed(1)}s`;
    function displaySrc(s){return (s&&s.previewUrl)?s.previewUrl:((s&&s.assetUrl)||'');}
    function readFileAsDataURL(file){return new Promise((resolve,reject)=>{const r=new FileReader(); r.onload=()=>resolve(String(r.result||'')); r.onerror=()=>reject(new Error('file read failed')); r.readAsDataURL(file);});}
    async function uploadImageToScene(sceneId,file){if(!file){return;} if(!/^image\//.test(file.type||'')){q('responseBox').value='Drop an image file (png/jpg/webp/gif/svg).'; addEvent('Rejected non-image drop.'); return;} const sc=state.scenes.find(x=>x.id===sceneId); if(!sc){return;} const base=q('bridgeUrlInput').value.trim(); try{const data=await readFileAsDataURL(file); const body={project_id:state.project.id,scene_id:sceneId,filename:file.name||'image.png',data}; const res=await fetch(base+'/api/asset-upload',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); const out=await res.json(); if(!out.ok){throw new Error(out.error||'upload failed');} sc.assetUrl=out.abs||out.path; sc.assetState='approved'; sc.reviewState='needs-review'; if(sc.status==='raw'||sc.status==='flagged') sc.status='ready'; sc.previewUrl=base+out.url; state.selectedSceneId=sceneId; q('responseBox').value=JSON.stringify(out,null,2); addEvent(`Dropped image onto ${sceneId}.`); renderAll();}catch(err){q('responseBox').value=String(err); addEvent('Image upload failed (is the bridge running?).');}}
    function recalc(){let cur=0; state.scenes.forEach((s,i)=>{s.order=i+1;s.start=Number(cur.toFixed(2));cur+=Number(s.duration)});} function totalDuration(){return state.scenes.reduce((a,b)=>a+Number(b.duration||0),0)} function scene(){return state.scenes.find(x=>x.id===state.selectedSceneId)||state.scenes[0]} function job(){return state.jobs.find(x=>x.id===state.selectedJobId)||state.jobs[0]}
    function replacementPlan(){return state.scenes.filter(s=>s.assetState==='needs-image'||s.status==='flagged'||!String(s.assetUrl||'').trim()).map((s,i)=>({scene_id:s.id,title:s.title,reason:s.status==='flagged'?'flagged scene':s.assetState==='needs-image'?'asset marked needs-image':'missing asset URL',search_prompt:`${s.title} ${s.notes||''} ${s.narration||''}`.trim(),fallback_asset:`generated-fallback-${String(i+1).padStart(3,'0')}.svg`,status:'needs-replacement'}));}
    function ensureAssets(){if(!Array.isArray(state.assets)) state.assets=[]; state.scenes.forEach((s,i)=>{if(s.assetUrl&&!state.assets.some(a=>a.url===s.assetUrl)){state.assets.push({id:`asset-${String(i+1).padStart(2,'0')}`,title:s.title,kind:s.assetState==='materialized'?'generated':'image',url:s.assetUrl});}}); return state.assets;}
    function payload(){return {storyboard:{id:state.project.id,title:state.project.title,aspect_ratio:state.project.aspect_ratio,pipeline_target:state.project.pipeline_target,workflow_stage:state.project.workflow_stage,task_id:state.project.task_id,total_duration_sec:Number(totalDuration().toFixed(2)),project_notes:state.projectNotes,voiceover_notes:state.voiceoverNotes,voice_settings:state.voiceSettings,assets:ensureAssets(),scenes:state.scenes.map(s=>{const c={...s}; delete c.previewUrl; return c;}),replacement_plan:replacementPlan()},launcher:{machine:state.selectedMachineId,engine:q('engineSelect').value,run_label:q('runLabelInput').value.trim(),execute:q('executeModeInput').value==='true'},mission_control:{open_task_id:state.project.task_id},checklist:state.checklist,validation_results:state.validationResults,events:state.events}}
    function renderWorkflow(){const wrap=q('workflowBar'); wrap.innerHTML=''; const current=state.stages.indexOf(state.project.workflow_stage); state.stages.forEach((stage,i)=>{const btn=document.createElement('button'); btn.className='workflow-step'+(stage===state.project.workflow_stage?' active':'')+(i<current?' done':''); btn.innerHTML=`<span><strong>${stage}</strong><br><span class="muted" style="font-size:12px">${i<current?'done':stage===state.project.workflow_stage?'current':'set stage'}</span></span><i data-lucide="${i<current?'check-circle-2':stage===state.project.workflow_stage?'play-circle':'circle'}"></i>`; btn.onclick=()=>{state.project.workflow_stage=stage; renderAll();}; wrap.appendChild(btn);});}
    function renderMachines(){const wrap=q('machineStack'); wrap.innerHTML=''; q('machineSelect').innerHTML=''; state.machines.forEach(m=>{const btn=document.createElement('button'); btn.className='machine-card'+(m.id===state.selectedMachineId?' active':''); btn.innerHTML=`<span><strong>${m.name}</strong><br><span class="muted" style="font-size:12px">${m.engine} · ${m.status}</span></span><span class="pill">${m.jobs} jobs</span>`; btn.onclick=()=>{state.selectedMachineId=m.id; renderAll();}; wrap.appendChild(btn); const opt=document.createElement('option'); opt.value=m.id; opt.textContent=`${m.name} (${m.status})`; q('machineSelect').appendChild(opt);}); q('machineSelect').value=state.selectedMachineId;}
    function renderJobs(){const wrap=q('jobStack'); wrap.innerHTML=''; state.jobs.forEach(j=>{const btn=document.createElement('button'); btn.className='job-card'+(j.id===state.selectedJobId?' active':''); btn.innerHTML=`<span><strong>${j.label}</strong><br><span class="muted" style="font-size:12px">${j.engine} · ${j.status}</span></span><span class="pill">${j.progress}%</span>`; btn.onclick=()=>{state.selectedJobId=j.id; renderAll();}; wrap.appendChild(btn);});}
    function renderChecklist(){const wrap=q('checklistStack'); wrap.innerHTML=''; state.checklist.forEach(item=>{const row=document.createElement('label'); row.className='check-item'; row.innerHTML=`<span><strong>${item.label}</strong></span><input class="checkbox" type="checkbox" ${item.done?'checked':''}>`; const input=row.querySelector('input'); input.onchange=e=>{item.done=e.target.checked; renderAll();}; wrap.appendChild(row);});}
    function renderEvents(){const wrap=q('eventStack'); wrap.innerHTML=''; state.events.slice().reverse().slice(0,6).forEach(evt=>{const row=document.createElement('div'); row.className='event-item'; row.innerHTML=`<span><strong>${evt.time}</strong> ${evt.text}</span><span class="pill">event</span>`; wrap.appendChild(row);});}
    function renderPreview(){const s=scene(); q('previewSceneCode').textContent=`Scene ${String(s.order).padStart(2,'0')}`; q('previewTitle').textContent=s.title; q('previewImage').src=displaySrc(s); q('durationBadge').textContent=fmt(s.duration); q('motionBadge').textContent=s.motionPreset; q('sceneStatusBadge').textContent=s.status; q('assetStateBadge').textContent=s.assetState; q('inspectorSceneCode').textContent=`Scene ${String(s.order).padStart(2,'0')}`; q('shotNameInput').value=s.title; q('assetUrlInput').value=s.assetUrl; q('durationInput').value=s.duration; q('transitionInput').value=s.transition; q('motionInput').value=s.motionPreset; q('statusInput').value=s.status; q('assetStateInput').value=s.assetState; q('captionInput').value=s.captionMode; q('notesInput').value=s.notes; q('narrationInput').value=s.narration||''; q('voStartInput').value=Number(s.voStart||0); q('voEndInput').value=Number(s.voEnd||0);}
    function renderScenes(){const wrap=q('sceneStack'); wrap.innerHTML=''; state.scenes.forEach(s=>{const btn=document.createElement('button'); btn.className='scene-card'+(s.id===state.selectedSceneId?' active':''); btn.draggable=true; btn.dataset.sceneId=s.id; btn.innerHTML=`<span style="display:flex;gap:10px;align-items:flex-start"><span class="thumb"><img src="${displaySrc(s)}" alt="${s.title}" width="270" height="480"></span><span class="stack" style="min-width:0"><span style="font-weight:800">${String(s.order).padStart(2,'0')}. ${s.title}</span><span class="muted">${fmt(s.duration)} · ${s.motionPreset} · ${s.transition}</span><span class="row"><span class="pill">${s.status}</span><span class="pill">${s.assetState}</span><span class="pill">${ReviewGate.reviewStateFor(s)}</span><span class="pill">${s.captionMode}</span></span></span></span><i data-lucide="grip-vertical"></i>`; btn.onclick=()=>{state.selectedSceneId=s.id; renderAll();}; btn.addEventListener('dragstart',e=>{e.dataTransfer.setData('text/plain',s.id);}); btn.addEventListener('dragover',e=>{e.preventDefault(); btn.classList.add('dropzone');}); btn.addEventListener('dragleave',()=>btn.classList.remove('dropzone')); btn.addEventListener('drop',e=>{e.preventDefault(); btn.classList.remove('dropzone'); if(e.dataTransfer.files&&e.dataTransfer.files.length){uploadImageToScene(s.id,e.dataTransfer.files[0]); return;} const fromId=e.dataTransfer.getData('text/plain'); if(fromId) reorderScene(fromId,s.id);}); wrap.appendChild(btn);});}
    function renderAssetLibrary(){const wrap=q('assetLibraryStack'); if(!wrap) return; wrap.innerHTML=''; ensureAssets().forEach(asset=>{const row=document.createElement('button'); row.className='asset-row'+(scene().assetUrl===asset.url?' active':''); const urlText=(asset.url||'').slice(0,44); row.innerHTML=`<span><strong>${asset.title||asset.id}</strong><br><span class="muted" style="font-size:12px">${asset.kind||'image'} · ${urlText}${(asset.url||'').length>44?'...':''}</span></span><span class="pill">asset</span>`; row.onclick=()=>{q('newAssetTitle').value=asset.title||''; q('newAssetUrl').value=asset.url||''; q('newAssetKind').value=asset.kind||'image';}; row.ondblclick=()=>assignSelectedAsset(asset); wrap.appendChild(row);});}
    function renderAssets(){const wrap=q('assetStack'); wrap.innerHTML=''; state.scenes.forEach(s=>{const row=document.createElement('button'); row.className='asset-row'+(s.id===state.selectedSceneId?' active':''); const urlText=(s.assetUrl||'').slice(0,42); row.innerHTML=`<span><strong>${s.title}</strong><br><span class="muted" style="font-size:12px">${s.assetState} · ${urlText}${(s.assetUrl||'').length>42?'...':''}</span><br><span class="muted" style="font-size:12px">VO ${Number(s.voStart||0).toFixed(1)}-${Number(s.voEnd||0).toFixed(1)}s</span></span><span class="pill">${s.status}</span>`; row.onclick=()=>{state.selectedSceneId=s.id; renderAll();}; wrap.appendChild(row);}); if(state.validationResults.length){state.validationResults.slice(0,8).forEach(v=>{const row=document.createElement('div'); row.className='event-item'; row.innerHTML=`<span><strong>${v.scene}</strong><br><span class="muted" style="font-size:12px">${v.message}</span></span><span class="pill">${v.status}</span>`; wrap.appendChild(row);});} renderAssetLibrary();}
    function renderPayload(){q('payloadBox').value=JSON.stringify(payload(),null,2);}
    function renderFormMeta(){q('aspectInput').value=state.project.aspect_ratio; if(q('pipelineTargetInput')) q('pipelineTargetInput').value=state.project.pipeline_target||'short-shorts'; q('taskIdInput').value=state.project.task_id; q('projectNotesInput').value=state.projectNotes; q('voiceoverNotesInput').value=state.voiceoverNotes; q('wpmInput').value=state.voiceSettings.wpm; q('voBufferInput').value=state.voiceSettings.buffer; q('executeModeInput').value=String(state.execute);}
    function renderTimeline(){const ruler=q('ruler'); ruler.innerHTML=''; const total=Math.ceil(totalDuration())+5; for(let i=0;i<=total;i++){const d=document.createElement('div'); d.textContent=`0:${String(i).padStart(2,'0')}`; ruler.appendChild(d);} const renderTrack=(el,type,labeler)=>{el.innerHTML=''; state.scenes.forEach(s=>{const clip=document.createElement('div'); clip.className=`clip ${type}`; clip.style.left=`${s.start*state.project.px}px`; clip.style.width=`${Math.max(58,s.duration*state.project.px)}px`; clip.innerHTML=`${type==='scene'?'<span class="handle left"></span><span class="handle right"></span>':''}<span>${labeler(s)}</span><span>${fmt(s.duration)}</span>`; if(type==='scene'){clip.dataset.sceneId=s.id; clip.querySelector('.handle.left').addEventListener('mousedown',e=>startResize(e,s.id,'left')); clip.querySelector('.handle.right').addEventListener('mousedown',e=>startResize(e,s.id,'right'));} el.appendChild(clip);});}; renderTrack(q('sceneTrack'),'scene',s=>s.title); renderTrack(q('motionTrack'),'motion',s=>s.motionPreset); renderTrack(q('textTrack'),'text',s=>s.captionMode); renderTrack(q('audioTrack'),'audio',s=>'Audio bed');}
    function renderAll(){recalc(); ensureAssets(); renderWorkflow(); renderMachines(); renderJobs(); renderChecklist(); renderEvents(); renderPreview(); renderScenes(); renderAssets(); renderPayload(); renderFormMeta(); renderTimeline(); if(window.lucide) lucide.createIcons(); updateBridgeStatusText();
    if(q('renderVideoBtn')) q('renderVideoBtn').disabled=!ReviewGate.allApproved(state.scenes);}
    function updateScene(patch){Object.assign(scene(),patch); renderAll();}
    function addEvent(text){const now=new Date(); const hh=String(now.getHours()).padStart(2,'0'); const mm=String(now.getMinutes()).padStart(2,'0'); state.events.push({time:`${hh}:${mm}`,text}); renderEvents();}
    function reorderScene(fromId,toId){if(fromId===toId) return; const fromIndex=state.scenes.findIndex(s=>s.id===fromId); const toIndex=state.scenes.findIndex(s=>s.id===toId); if(fromIndex<0||toIndex<0) return; const [item]=state.scenes.splice(fromIndex,1); state.scenes.splice(toIndex,0,item); addEvent(`Reordered ${fromId} before/around ${toId}.`); renderAll();}
    function addScene(){const id=`scene-${String(state.scenes.length+1).padStart(2,'0')}`; state.scenes.push({id,title:`New scene ${state.scenes.length+1}`,assetUrl:'https://picsum.photos/seed/newscene/1080/1920',duration:3.0,start:totalDuration(),transition:'fade',motionPreset:'zoom-in',status:'raw',assetState:'needs-image',captionMode:'none',notes:'Replace with notes.'}); state.selectedSceneId=id; addEvent(`Added ${id}.`); renderAll();}
    function duplicateScene(){const s=scene(); const clone=JSON.parse(JSON.stringify(s)); clone.id=`scene-${Date.now()}`; clone.title=s.title+' copy'; clone.status='raw'; state.scenes.push(clone); state.selectedSceneId=clone.id; addEvent(`Duplicated ${s.id}.`); renderAll();}
    function startResize(e,sceneId,edge){e.preventDefault(); const startX=e.clientX; const target=state.scenes.find(s=>s.id===sceneId); const initial=target.duration; function move(ev){const delta=(ev.clientX-startX)/state.project.px; if(edge==='right'){target.duration=Math.max(.5,Number((initial+delta).toFixed(1)));} else {const next=Math.max(.5,Number((initial-delta).toFixed(1))); target.duration=next;} renderAll();} function up(){document.removeEventListener('mousemove',move); document.removeEventListener('mouseup',up); addEvent(`Resized ${sceneId} to ${target.duration.toFixed(1)}s.`);} document.addEventListener('mousemove',move); document.addEventListener('mouseup',up);}
    function saveLocal(){localStorage.setItem('storyboard-ultimate-workflow',JSON.stringify(state)); addEvent('Saved local state.');}
    function loadLocal(){const raw=localStorage.getItem('storyboard-ultimate-workflow'); if(!raw) return; const parsed=JSON.parse(raw); Object.assign(state,parsed); renderAll(); addEvent('Loaded local state.');}
    function exportBundle(){const blob=new Blob([JSON.stringify(payload(),null,2)],{type:'application/json'}); const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download=`${state.project.id}-bundle.json`; a.click(); URL.revokeObjectURL(a.href); addEvent('Exported workflow bundle.');}
    function normalizeImportedScene(raw,index){return {id:String(raw.id||raw.scene_id||`scene-${String(index).padStart(2,'0')}`),title:String(raw.title||raw.scene_description||`Scene ${index}`),assetUrl:String(raw.assetUrl||raw.asset_url||raw.asset||''),duration:Math.max(.5,Number(raw.duration||raw.hold_seconds||raw.vo_seconds||3)),start:Number(raw.start||0),transition:String(raw.transition||'fade'),motionPreset:String(raw.motionPreset||raw.motion||raw.motion_preset||'zoom-in'),status:String(raw.status||'raw'),assetState:String(raw.assetState||raw.asset_state||'approved'),captionMode:String(raw.captionMode||raw.caption_mode||'none'),notes:String(raw.notes||raw.prompt_notes||''),narration:String(raw.narration||raw.script||raw.narration_text||''),voStart:Number(raw.voStart||raw.vo_start||0),voEnd:Number(raw.voEnd||raw.vo_end||0)};}
    function applyPayloadObject(obj){const sb=obj.storyboard&&typeof obj.storyboard==='object'?obj.storyboard:obj; const launcher=obj.launcher&&typeof obj.launcher==='object'?obj.launcher:{}; const scenes=Array.isArray(sb.scenes)?sb.scenes:[]; if(!scenes.length) throw new Error('Imported payload has no storyboard.scenes or scenes array.'); state.project.id=String(sb.id||state.project.id); state.project.title=String(sb.title||sb.project_title||state.project.title); state.project.aspect_ratio=String(sb.aspect_ratio||state.project.aspect_ratio); state.project.pipeline_target=String(sb.pipeline_target||state.project.pipeline_target||'short-shorts'); state.project.workflow_stage=String(sb.workflow_stage||state.project.workflow_stage); state.project.task_id=String(sb.task_id||state.project.task_id); state.projectNotes=String(sb.project_notes||obj.project_notes||state.projectNotes); state.voiceoverNotes=String(sb.voiceover_notes||obj.voiceover_notes||state.voiceoverNotes); if(sb.voice_settings) state.voiceSettings={...state.voiceSettings,...sb.voice_settings}; state.assets=Array.isArray(sb.assets)?sb.assets.map((a,i)=>({id:String(a.id||`asset-${String(i+1).padStart(2,'0')}`),title:String(a.title||a.name||`Asset ${i+1}`),kind:String(a.kind||a.asset_type||'image'),url:String(a.url||a.asset||a.local_path||a.source_url||'')})):[]; state.scenes=scenes.map((s,i)=>normalizeImportedScene(s,i+1)); state.selectedSceneId=state.scenes[0].id; if(launcher.machine) state.selectedMachineId=launcher.machine; if(launcher.engine&&q('engineSelect')) q('engineSelect').value=launcher.engine; if(launcher.run_label&&q('runLabelInput')) q('runLabelInput').value=launcher.run_label; if(typeof launcher.execute==='boolean') state.execute=launcher.execute; addEvent('Applied imported storyboard JSON.'); renderAll();}
    function applyPayloadText(){try{applyPayloadObject(JSON.parse(q('payloadBox').value));}catch(err){q('responseBox').value=String(err); addEvent('Payload apply failed.');}}
    function importJsonFile(file){if(!file) return; const reader=new FileReader(); reader.onload=()=>{try{const obj=JSON.parse(String(reader.result||'')); applyPayloadObject(obj);}catch(err){q('responseBox').value=String(err); addEvent('JSON import failed.');}}; reader.readAsText(file);}
    function addAsset(){const url=q('newAssetUrl').value.trim(); if(!url){q('responseBox').value='Asset URL or path is required.'; return;} const title=q('newAssetTitle').value.trim()||`Asset ${ensureAssets().length+1}`; const kind=q('newAssetKind').value||'image'; const existing=ensureAssets().find(a=>a.url===url); if(existing){existing.title=title; existing.kind=kind;} else {state.assets.push({id:`asset-${Date.now()}`,title,kind,url});} addEvent(`Added asset ${title}.`); renderAll();}
    function assignSelectedAsset(asset){const chosen=asset||ensureAssets().find(a=>a.url===q('newAssetUrl').value.trim()); if(!chosen||!chosen.url){q('responseBox').value='Choose or add an asset before assigning.'; return;} updateScene({assetUrl:chosen.url,assetState:chosen.kind==='generated'?'materialized':'approved'}); addEvent(`Assigned asset to ${scene().id}.`);}

    
    function countWords(text){return (String(text||'').trim().match(/\b\w+\b/g)||[]).length;}
    function autoFillVoTimings(){
      const wpm=Math.max(80, Number(state.voiceSettings.wpm||132));
      const buffer=Math.max(0, Number(state.voiceSettings.buffer||0.3));
      let cursor=0;
      state.scenes.forEach(s=>{
        const words=countWords(s.narration||'');
        const speechSeconds=words>0 ? (words / wpm) * 60 : Math.max(1.2, Number(s.duration||0) * 0.55);
        const sceneSpan=Math.max(0.8, Number(s.duration||0));
        const voLen=Math.min(sceneSpan, Number((speechSeconds + buffer).toFixed(1)));
        s.voStart=Number((cursor + 0.05).toFixed(1));
        s.voEnd=Number((s.voStart + Math.max(0.6, voLen - 0.05)).toFixed(1));
        if(s.voEnd > s.start + sceneSpan){ s.voEnd=Number((s.start + sceneSpan - 0.05).toFixed(1)); }
        cursor=s.start + sceneSpan;
      });
      addEvent('Auto-filled VO timings from narration.');
      renderAll();
    }
    function suggestPacing(){
      const suggestions=state.scenes.map(s=>{
        const words=countWords(s.narration||'');
        const desired=Math.max(1.4, Number((((words / Math.max(80,state.voiceSettings.wpm))*60) + state.voiceSettings.buffer).toFixed(1)));
        return {scene:s.id, current:s.duration, suggested:desired, delta:Number((desired - s.duration).toFixed(1))};
      });
      q('responseBox').value=JSON.stringify({type:'pacing-suggestions', wpm:state.voiceSettings.wpm, buffer:state.voiceSettings.buffer, suggestions}, null, 2);
      addEvent('Generated pacing suggestions.');
    }

    function fitDurationsToNarration(){
      const wpm=Math.max(80, Number(state.voiceSettings.wpm||132));
      const buffer=Math.max(0, Number(state.voiceSettings.buffer||0.3));
      state.scenes.forEach(s=>{
        const words=countWords(s.narration||'');
        const speechSeconds=words>0 ? (words / wpm) * 60 : Math.max(1.2, Number(s.duration||0) * 0.55);
        const target=Math.max(1.4, Number((speechSeconds + buffer + 0.25).toFixed(1)));
        s.duration=target;
      });
      recalc();
      autoFillVoTimings();
      addEvent('Auto-fit scene durations to narration length.');
      renderAll();
    }

    function validateScenes(){
      const results=[];
      state.scenes.forEach(s=>{
        if(!s.assetUrl || !String(s.assetUrl).trim()) results.push({scene:s.id,status:'fail',message:'Missing asset URL.'});
        if(!(Number(s.duration)>0)) results.push({scene:s.id,status:'fail',message:'Duration must be greater than 0.'});
        if(s.status==='flagged') results.push({scene:s.id,status:'warn',message:'Scene is flagged and should be reviewed before launch.'});
        if(s.assetState==='needs-image') results.push({scene:s.id,status:'warn',message:'Scene still needs an approved image.'});
        if(!s.narration || !String(s.narration).trim()) results.push({scene:s.id,status:'warn',message:'Narration/script text is empty.'});
        if(Number(s.voEnd||0) < Number(s.voStart||0)) results.push({scene:s.id,status:'fail',message:'VO end is earlier than VO start.'});
        if(Number(s.voEnd||0) > Number(s.start||0) + Number(s.duration||0) + 0.25) results.push({scene:s.id,status:'warn',message:'VO extends beyond scene duration.'});
      });
      if(!results.length) results.push({scene:'all',status:'pass',message:'All scenes passed validation.'});
      state.validationResults=results;
      addEvent('Ran scene validation.');
      renderAll();
      return results;
    }
    function buildEditorHandoff(){
      const handoff={
        editor:{target:['Shotcut','DaVinci Resolve'],notes:state.projectNotes,voiceover_notes:state.voiceoverNotes},
        replacement_plan:replacementPlan(),
        timeline:state.scenes.map(s=>({
          scene_id:s.id,title:s.title,start:s.start,duration:s.duration,asset:s.assetUrl,transition:s.transition,motion:s.motionPreset,
          narration:s.narration,vo_start:s.voStart,vo_end:s.voEnd,caption_mode:s.captionMode,status:s.status,asset_state:s.assetState
        }))
      };
      const blob=new Blob([JSON.stringify(handoff,null,2)],{type:'application/json'});
      const a=document.createElement('a');
      a.href=URL.createObjectURL(blob);
      a.download=`${state.project.id}-editor-handoff.json`;
      a.click();
      URL.revokeObjectURL(a.href);
      addEvent('Exported editor handoff bundle.');
    }
    function updateBridgeStatusText(){const flagged=state.scenes.filter(s=>s.status==='flagged').length; const missing=state.scenes.filter(s=>s.assetState==='needs-image').length; q('bridgeStatus').textContent=`${state.project.workflow_stage.toUpperCase()} stage · ${state.jobs.length} jobs tracked · ${flagged} flagged · ${missing} needing images.`;}
    async function pingBridge(){const base=q('bridgeUrlInput').value.trim(); try{const res=await fetch(base+'/api/status'); const text=await res.text(); q('responseBox').value=text; addEvent('Pinged bridge successfully.');}catch(err){q('responseBox').value=String(err); addEvent('Bridge ping failed.');}}
    async function pollJobs(){const base=q('bridgeUrlInput').value.trim(); try{const res=await fetch(base+'/api/status'); const data=await res.json(); if(Array.isArray(data.jobs)){ state.jobs=data.jobs.slice(-8).map((j,i)=>({id:`polled-${i}`,label:j.job,machineId:state.selectedMachineId,engine:q('engineSelect').value,status:'written',progress:100})); if(state.jobs[0]) state.selectedJobId=state.jobs[0].id; } q('responseBox').value=JSON.stringify(data,null,2); addEvent('Polled bridge jobs.'); renderAll(); }catch(err){q('responseBox').value=String(err); addEvent('Job poll failed.');}}
    async function sendToBridge(execute){const issues=validateScenes(); if(issues.some(x=>x.status==='fail') || issues.some(x=>x.status==='warn' && /flagged|needs an approved image/i.test(x.message))){ q('responseBox').value=JSON.stringify({ok:false,message:'Validation blocked launch until warnings/failures are reviewed.',validation:issues},null,2); addEvent('Launch blocked by validation.'); return; } const base=q('bridgeUrlInput').value.trim(); state.execute=execute; const body={machine:state.selectedMachineId,engine:q('engineSelect').value,run_label:q('runLabelInput').value.trim() || 'storyboard-ultimate-001',execute, payload:payload()}; try{const res=await fetch(base+'/api/launch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); const text=await res.text(); q('responseBox').value=text; state.project.workflow_stage=execute?'render':'export'; state.jobs.unshift({id:`job-${Date.now()}`,label:body.run_label,machineId:state.selectedMachineId,engine:body.engine,status:execute?'launched':'written',progress:execute?10:100}); state.selectedJobId=state.jobs[0].id; const m=state.machines.find(x=>x.id===state.selectedMachineId); if(m) m.jobs+=1; addEvent(execute?'Sent payload and requested execute.':'Sent payload to bridge.'); renderAll();}catch(err){q('responseBox').value=String(err); addEvent('Bridge send failed.');}}
    async function generateImages(){
      const issues=validateScenes();
      if(issues.some(x=>x.status==='fail')){ q('responseBox').value=JSON.stringify({ok:false,message:'Fix validation failures before generating.',validation:issues},null,2); addEvent('Generate blocked by validation.'); return; }
      const base=q('bridgeUrlInput').value.trim();
      const body={machine:state.selectedMachineId,engine:q('engineSelect').value,run_label:q('runLabelInput').value.trim()||'storyboard-ultimate-001',execute:true,action:'materialize',payload:payload()};
      try{
        const res=await fetch(base+'/api/launch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
        const out=await res.json();
        q('responseBox').value=JSON.stringify(out,null,2);
        if(!out.ok){throw new Error(out.error||'generate failed');}
        if(out.status!=='executed'){ q('responseBox').value='Dry-run: no images generated. Start the bridge with STORYBOARD_BRIDGE_LIVE=1 to generate images.\n\n'+JSON.stringify(out,null,2); addEvent('Generate skipped: bridge in dry-run mode.'); return; }
        state.currentJobId=out.job_id;
        if(Array.isArray(out.scenes)&&out.scenes.length){ state.scenes=ReviewGate.applyMaterializeResult(state.scenes,out,base); }
        state.project.workflow_stage='approve';
        addEvent(`Generated images for ${out.job_id}. Review each scene.`);
        renderAll();
      }catch(err){ q('responseBox').value=String(err); addEvent('Generate failed (is the bridge running with STORYBOARD_BRIDGE_LIVE=1?).'); }
    }

    async function renderVideo(){
      if(!ReviewGate.allApproved(state.scenes)){ q('responseBox').value=JSON.stringify({ok:false,message:'Approve every scene before rendering.'},null,2); addEvent('Render blocked: not all scenes approved.'); return; }
      if(!state.currentJobId){ q('responseBox').value=JSON.stringify({ok:false,message:'Generate images first so there is a job to render.'},null,2); return; }
      const base=q('bridgeUrlInput').value.trim();
      const body={machine:state.selectedMachineId,engine:q('engineSelect').value,run_label:q('runLabelInput').value.trim()||'storyboard-ultimate-001',execute:true,action:'render',job_id:state.currentJobId,payload:payload()};
      try{
        const res=await fetch(base+'/api/launch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
        const out=await res.json();
        q('responseBox').value=JSON.stringify(out,null,2);
        if(!out.ok){throw new Error(out.error||'render failed');}
        state.project.workflow_stage='render';
        addEvent(out.final_video?`Rendered: ${out.final_video}`:'Render requested (dry-run or pending).');
        renderAll();
      }catch(err){ q('responseBox').value=String(err); addEvent('Render failed (is the bridge running with STORYBOARD_BRIDGE_LIVE=1?).'); }
    }

    var findState={open:false,tab:'generate',results:[],busy:false};
    function findBase(){return q('bridgeUrlInput').value.trim();}
    function closeFindPanel(){findState.open=false; q('findPanel').hidden=true;}
    function openFindPanel(){findState.open=true; q('findPanel').hidden=false; findState.tab='generate'; findState.results=[]; const s=scene(); findState.query=FindImages.defaultQueryForScene(s); renderFindPanel();}
    function setFindTab(tab){findState.tab=tab; findState.results=[]; renderFindPanel();}
    function pickFindResult(index){const pick=findState.results[index]; if(!pick) return; const patched=FindImages.assignPick(scene(),pick,findState.tab,findBase()); updateScene({assetUrl:patched.assetUrl,previewUrl:patched.previewUrl,assetState:patched.assetState,reviewState:patched.reviewState}); addEvent(`Assigned ${findState.tab} image to ${scene().id}.`); closeFindPanel();}
    async function runGenerate(){const base=findBase(); const prompt=(q('findQuery')?q('findQuery').value:findState.query||'').trim(); if(!prompt){setFindStatus('Enter a prompt first.'); return;} findState.busy=true; setFindStatus('Generating...'); try{const res=await fetch(base+'/api/generate-image',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt,aspect_ratio:state.project.aspect_ratio})}); const out=await res.json(); findState.busy=false; if(!out.ok){setFindStatus(out.error||'Generate failed.'); return;} findState.results=FindImages.parseResults('generate',out); renderFindResults(); setFindStatus('Generated. Click it to use, or Regenerate.');}catch(err){findState.busy=false; setFindStatus('Generate failed (is the bridge running with STORYBOARD_BRIDGE_LIVE=1?).');}}
    async function runSearch(kind){const base=findBase(); const query=(q('findQuery')?q('findQuery').value:'').trim(); if(!query){setFindStatus('Enter a search term first.'); return;} setFindStatus('Searching...'); try{const path=kind==='stock'?'/api/search-stock?q=':'/api/search-web?q='; const res=await fetch(base+path+encodeURIComponent(query)); const out=await res.json(); if(!out.ok){setFindStatus(out.need_key?`Add ${out.need_key} to the bridge environment to enable ${kind} search.`:(out.error||'Search failed.')); findState.results=[]; renderFindResults(); return;} findState.results=FindImages.parseResults(kind,out); renderFindResults(); setFindStatus(findState.results.length?`${findState.results.length} results. Click one to use it.`:'No results.');}catch(err){setFindStatus(`${kind} search failed (is the bridge running?).`);}}
    function setFindStatus(msg){const el=q('findStatus'); if(el) el.textContent=msg;}
    function renderFindResults(){const grid=q('findGrid'); if(!grid) return; grid.innerHTML=''; findState.results.forEach((r,i)=>{const cell=document.createElement('button'); cell.type='button'; cell.style.cssText='border:1px solid #30363d;border-radius:8px;overflow:hidden;padding:0;background:#0d1117;cursor:pointer'; const img=document.createElement('img'); var _src=r.thumb||r.full; img.src=(_src && _src.charAt(0)==='/')?(findBase()+_src):_src; img.alt=''; img.style.cssText='width:100%;height:120px;object-fit:cover;display:block'; cell.appendChild(img); cell.onclick=()=>pickFindResult(i); grid.appendChild(cell);});}
    function renderFindPanel(){const p=q('findPanel'); if(!p) return; const tabs=['generate','stock','web']; p.innerHTML=`<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px"><strong>Find images · ${scene().id}</strong><button type="button" id="findClose" class="btn">Close</button></div><div style="display:flex;gap:6px;margin-bottom:10px">${tabs.map(t=>`<button type="button" class="btn" data-tab="${t}" style="${t===findState.tab?'outline:2px solid #6ca8ff':''}">${t}</button>`).join('')}</div><div style="display:flex;gap:6px;margin-bottom:8px"><input id="findQuery" value="${(findState.query||'').replace(/"/g,'&quot;')}" style="flex:1;padding:8px;border-radius:8px;border:1px solid #30363d;background:#0d1117;color:#e6edf3"><button type="button" id="findGo" class="btn">${findState.tab==='generate'?'Generate':'Search'}</button>${findState.tab==='generate'?'<button type="button" id="findRegen" class="btn">Regenerate</button>':''}</div><div id="findStatus" class="muted" style="font-size:12px;margin-bottom:8px"></div><div id="findGrid" style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px"></div>`; q('findClose').onclick=closeFindPanel; p.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>setFindTab(b.dataset.tab)); q('findGo').onclick=onFindGo; if(q('findRegen')) q('findRegen').onclick=runGenerate; renderFindResults();}
    function onFindGo(){if(findState.tab==='generate'){runGenerate();}else{runSearch(findState.tab);}}

    function toggleTheme(){const root=document.documentElement; root.setAttribute('data-theme',root.getAttribute('data-theme')==='dark'?'light':'dark'); if(window.lucide) lucide.createIcons();}

    q('addSceneBtn').onclick=addScene; q('duplicateSceneBtn').onclick=duplicateScene; q('recalcBtn').onclick=()=>{recalc(); addEvent('Recalculated scene starts.'); renderAll();}; q('themeBtn').onclick=toggleTheme; q('saveLocalBtn').onclick=saveLocal; q('loadLocalBtn').onclick=loadLocal;
    q('pingBridgeBtn').onclick=pingBridge; q('pollJobsBtn').onclick=pollJobs; q('importJsonBtn').onclick=()=>q('jsonFileInput').click(); q('jsonFileInput').onchange=e=>importJsonFile(e.target.files&&e.target.files[0]); q('exportBundleBtn').onclick=exportBundle; q('refreshPayloadBtn').onclick=renderPayload; q('applyPayloadBtn').onclick=applyPayloadText; q('sendBridgeBtn').onclick=()=>sendToBridge(false); q('sendExecuteBtn').onclick=()=>sendToBridge(true);
    q('generateImagesBtn').onclick=generateImages; q('renderVideoBtn').onclick=renderVideo;
    if(q('findImagesBtn')) q('findImagesBtn').onclick=openFindPanel;
    q('machineSelect').onchange=e=>{state.selectedMachineId=e.target.value; renderAll();}; q('aspectInput').onchange=e=>{state.project.aspect_ratio=e.target.value; renderAll();}; if(q('pipelineTargetInput')) q('pipelineTargetInput').onchange=e=>{state.project.pipeline_target=e.target.value; renderAll();}; q('taskIdInput').oninput=e=>{state.project.task_id=e.target.value; renderAll();}; q('projectNotesInput').oninput=e=>{state.projectNotes=e.target.value; renderAll();}; q('executeModeInput').onchange=e=>{state.execute=e.target.value==='true'; renderAll();}; q('engineSelect').onchange=renderPayload; q('runLabelInput').oninput=renderPayload;
    [['shotNameInput','title'],['assetUrlInput','assetUrl'],['transitionInput','transition'],['motionInput','motionPreset'],['statusInput','status'],['assetStateInput','assetState'],['captionInput','captionMode'],['notesInput','notes'],['narrationInput','narration']].forEach(([id,key])=>{q(id).addEventListener('input',e=>updateScene({[key]:e.target.value})); q(id).addEventListener('change',e=>updateScene({[key]:e.target.value}));});
    q('assetUrlInput').addEventListener('change',()=>updateScene({reviewState:'needs-review'}));
    q('durationInput').addEventListener('input',e=>updateScene({duration:Math.max(.5,Number(e.target.value||.5))})); q('voStartInput').addEventListener('input',e=>updateScene({voStart:Number(e.target.value||0)})); q('voEndInput').addEventListener('input',e=>updateScene({voEnd:Number(e.target.value||0)}));
    q('voiceoverNotesInput').oninput=e=>{state.voiceoverNotes=e.target.value; renderAll();}; q('wpmInput').oninput=e=>{state.voiceSettings.wpm=Number(e.target.value||132); renderAll();}; q('voBufferInput').oninput=e=>{state.voiceSettings.buffer=Number(e.target.value||0.3); renderAll();}; q('validateBtn').onclick=validateScenes; q('autoVoBtn').onclick=autoFillVoTimings; q('fitDurationsBtn').onclick=fitDurationsToNarration; q('paceSuggestBtn').onclick=suggestPacing; q('editorHandoffBtn').onclick=buildEditorHandoff; q('addAssetBtn').onclick=addAsset; q('assignAssetBtn').onclick=()=>assignSelectedAsset();
    q('readyBtn').onclick=()=>updateScene({status:'ready'}); q('approveBtn').onclick=()=>updateScene({status:'approved',reviewState:'approved'}); q('flagBtn').onclick=()=>updateScene({status:'flagged',reviewState:'flagged'}); q('zoomInBtn').onclick=()=>{state.project.px=Math.min(120,state.project.px+8); renderAll();}; q('zoomOutBtn').onclick=()=>{state.project.px=Math.max(28,state.project.px-8); renderAll();};
    (function(){const pv=document.querySelector('.preview'); if(!pv) return; pv.addEventListener('dragover',e=>{e.preventDefault(); pv.classList.add('dropzone');}); pv.addEventListener('dragleave',()=>pv.classList.remove('dropzone')); pv.addEventListener('drop',e=>{e.preventDefault(); pv.classList.remove('dropzone'); if(e.dataTransfer.files&&e.dataTransfer.files.length){uploadImageToScene(state.selectedSceneId,e.dataTransfer.files[0]);}});})();
    renderAll(); if(window.lucide) lucide.createIcons();
