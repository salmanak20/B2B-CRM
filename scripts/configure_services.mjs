// Vercel's documented Services model keeps Vite and FastAPI on one origin.
import fs from 'node:fs';
const frontend=JSON.parse(fs.readFileSync('stitch_crm_pro_enterprise_suite/vercel.json','utf8'));
frontend.installCommand='npm ci --include=dev';
// Explicit file destinations avoid cleanUrls redirects losing the HTML route in Services.
frontend.cleanUrls=false;
frontend.rewrites=frontend.rewrites.filter(r=>!r.source.startsWith('/api/')&&r.source!=='/:path*/code').map(r=>({...r,destination:r.destination.replace(/\.html$/,'')+'.html'}));
frontend.rewrites.push({source:'/:path*/code',destination:'/:path*/code.html'});
fs.writeFileSync('stitch_crm_pro_enterprise_suite/vercel.json',JSON.stringify(frontend,null,2)+'\n');
const config={
  $schema:'https://openapi.vercel.sh/vercel.json',
  services:{
    frontend:{root:'stitch_crm_pro_enterprise_suite',...frontend,devCommand:'npm run dev -- --host 127.0.0.1'},
    backend:{root:'backend',framework:'fastapi',entrypoint:'app.main:app',
      functions:{'app/main.py':{excludeFiles:'{.venv/**,.env,.env.*,tests/**,.backups/**,__pycache__/**,**/__pycache__/**,alembic/**,*.log}'}}}
  },
  rewrites:[{source:'/api/v1/:path*',destination:{service:'backend'}},{source:'/(.*)',destination:{service:'frontend'}}],
  headers:frontend.headers
};
fs.writeFileSync('vercel.json',JSON.stringify(config,null,2)+'\n');
