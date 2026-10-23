import {defineConfig,loadEnv} from 'vite';
import {resolve} from 'node:path';
import {readdirSync,existsSync,mkdirSync,readFileSync,writeFileSync} from 'node:fs';

const routes={'/platform-admin/login':'platform_admin_login','/usage':'subscription_crm_pro','/subscription':'subscription_crm_pro','/platform-admin':'platform_admin_crm_pro','/login':'crm_pro_enterprise','/dashboard':'analytics_reports_crm_pro','/analytics':'analytics_reports_crm_pro','/reports':'analytics_reports_crm_pro','/companies':'companies_crm_pro','/contacts':'contacts_crm_pro','/leads':'leads_management_crm_pro','/deals':'workflow_automation_crm_pro','/tasks':'tasks_activities_crm_pro','/notifications':'notifications_crm_pro','/users':'user_management_crm_pro','/settings':'settings_crm_pro','/team':'team_performance_crm_pro','/automations':'automations_crm_pro','/calendar':'calendar_crm_pro'};

function cleanRoutes(desktop){
  const setup=server=>{server.middlewares.use((req,res,next)=>{const [path,query]=req.url.split('?');const route=path.replace(/\.html$/,'');if(routes[path]||routes[route])req.url='/'+routes[routes[path]?path:route]+'/code.html'+(query?'?'+query:'');next();});};
  return {
    name:'crm-clean-routes',
    configureServer:setup,
    configurePreviewServer:setup,
    transformIndexHtml:undefined,
    writeBundle:desktop?function(options){
      const outDir=resolve(options.dir||'dist');
      for(const [route,entry] of Object.entries(routes)){
        const sourceFile=resolve(outDir,entry,'code.html');
        if(!existsSync(sourceFile))throw new Error(`Missing desktop route entry ${entry}/code.html for ${route}`);
        const destination=resolve(outDir,`${route.replace(/^\//,'')}.html`);
        mkdirSync(resolve(destination,'..'),{recursive:true});
        writeFileSync(destination,readFileSync(sourceFile));
      }
    }:undefined,
  };
}

export default defineConfig(({mode})=>{
  const env=loadEnv(mode,process.cwd(),'');
  const desktop=mode==='desktop';
  if(desktop){
    let api;
    try{api=new URL(env.VITE_API_BASE_URL||'');}catch{throw new Error('Desktop builds require VITE_API_BASE_URL, an absolute HTTPS URL ending in /api/v1.');}
    if((api.protocol!=='https:'&&!['localhost','127.0.0.1'].includes(api.hostname))||api.pathname.replace(/\/$/,'')!='/api/v1'||api.search||api.hash)throw new Error('VITE_API_BASE_URL must be an HTTPS URL ending in /api/v1 (HTTP is allowed only for localhost).');
  }
  const proxy={'/api':{target:env.API_BACKEND_ORIGIN||'http://127.0.0.1:8000',changeOrigin:true}};
  const input={index:resolve('index.html')};
  for(const dir of readdirSync('.', {withFileTypes:true}).filter(d=>d.isDirectory()))if(existsSync(resolve(dir.name,'code.html')))input[dir.name]=resolve(dir.name,'code.html');
  return {plugins:[cleanRoutes(desktop)],server:{host:'127.0.0.1',proxy},preview:{host:'127.0.0.1',proxy},build:{rolldownOptions:{input}}};
});
