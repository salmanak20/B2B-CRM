import {existsSync,readFileSync,readdirSync} from 'node:fs';
import {join} from 'node:path';

const dist=join(process.cwd(),'dist');
const routes=['platform-admin/login','usage','subscription','platform-admin','login','dashboard','analytics','reports','companies','contacts','leads','deals','tasks','notifications','users','settings','team','automations','calendar'];
const missing=routes.map(route=>join(dist,`${route}.html`)).filter(path=>!existsSync(path));
if(missing.length)throw new Error(`Desktop route build is missing ${missing.length} static route file(s).`);
const javascript=readdirSync(join(dist,'assets')).filter(name=>name.endsWith('.js')).map(name=>readFileSync(join(dist,'assets',name),'utf8')).join('\n');
if(!javascript.includes('/api/v1')||!javascript.includes('b2-b-crm.vercel.app')||!javascript.includes('desktop_navigation-'))throw new Error('Desktop bundle does not contain its API endpoint and navigation support.');
console.log(`Desktop build contains ${routes.length} route pages, client navigation and the configured public API origin.`);
