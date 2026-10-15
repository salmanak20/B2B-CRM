import {checkAuth} from './auth.js';
import '../css/app.css';
try{const user=await checkAuth();location.replace(user?'/dashboard':'/login');}catch{document.body.textContent='Unable to reach CRM Pro. Please reload when your connection is restored.';}
