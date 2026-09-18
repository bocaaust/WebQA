// DOM integration test; this does not claim a rendered-browser acceptance run.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');
const site = {id:'site-100680ad546c',url:'https://example.com',page_lines:'',has_tests:false,latest_result:null};
const calls = [];
const answer = {kind:'proposal',site:site.id,proposal:'a'.repeat(32),summary:'Check the home page',tests:[{priority:'P1',why:'Check accessibility'}],validation:{assumptions:[],changes:{added:['home'],modified:[],removed:[]}},diff:'Example controlled test diff',applied:false};
const dom = new JSDOM(fs.readFileSync(path.join(__dirname,'../../src/webqa/app.html'),'utf8'), {
  url:'http://127.0.0.1:8765',runScripts:'dangerously',beforeParse(window) {
    window.HTMLElement.prototype.scrollIntoView = function() {};
    window.HTMLAnchorElement.prototype.click = function() {};
    window.URL.createObjectURL = () => 'blob:controlled-download';
    window.URL.revokeObjectURL = () => {};
    window.document.addEventListener('click',e=>{if(e.target.tagName==='A')e.preventDefault();});
    window.fetch = async (route,options={}) => {
      const data = options.body ? JSON.parse(options.body) : null;
      calls.push({route,data});
      let result;
      if(route==='/api/state') result={websites:[site],active_job:null,cloud_inbox:'/app/Cloud-Inbox'};
      else if(route==='/api/models') result={models:[],available:false};
      else if(route==='/api/cloud/export') result={filename:'request.webqa-request.json',request:{operation:data.operation}};
      else if(route==='/api/cloud/scan') result={folder:'/app/Cloud-Inbox',files:[{file:'result.webqa-result.json',operation:'develop',status:'ready',site:site.id}]};
      else if(route==='/api/cloud/import') result=answer;
      else if(route==='/api/apply'){site.has_tests=true;result={message:'Tests saved.'};}
      else throw new Error('Unexpected request: '+route);
      return {ok:true,json:async()=>result};
    };
  }
});
const $ = id => dom.window.document.getElementById(id);
async function until(predicate) {for(let i=0;i<100;i++){if(predicate())return;await new Promise(r=>setTimeout(r,5));}throw new Error('UI did not reach expected state');}
(async()=>{
  await until(()=>$('saved').options.length===2);
  $('saved').value=site.id;$('saved').dispatchEvent(new dom.window.Event('change'));
  assert.equal($('author').disabled,true,'Local AI requires a model');
  $('processor').value='colab';$('processor').dispatchEvent(new dom.window.Event('change'));
  assert.equal($('author').disabled,false,'Cloud mode needs no local Ollama');
  assert.equal($('author').textContent,'Export test request');
  assert.equal(dom.window.modelSettings().model,null);
  $('request').value='Create a homepage accessibility test';$('author').click();
  await until(()=>calls.some(c=>c.route==='/api/cloud/export'));
  assert.equal(calls.find(c=>c.route==='/api/cloud/export').data.operation,'develop');
  $('scan-inbox').click();await until(()=>$('inbox-files').querySelector('button'));
  $('inbox-files').querySelector('button').click();
  await until(()=>!$('review').classList.contains('hidden')&&!$('apply').disabled);
  assert.equal($('review-summary').textContent,'Check the home page');
  assert.equal(site.has_tests,false,'Import alone cannot apply tests');
  $('apply').click();await until(()=>!$('run-custom').disabled);
  assert.equal(site.has_tests,true);
  assert(!calls.some(c=>c.route==='/api/author'||c.route==='/api/explain'));
  console.log('Dashboard DOM integration passed: cloud mode, export, scan, review, apply, and local run enabled.');
  dom.window.close();
})().catch(error=>{console.error(error);dom.window.close();process.exitCode=1;});
