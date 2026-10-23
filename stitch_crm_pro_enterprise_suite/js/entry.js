import {checkAuth} from './auth.js';
import {navigate} from './config.js';
import '../css/app.css';
try{const user=await checkAuth();navigate(user?'/dashboard':'/login',{replace:true});}catch{document.body.textContent='Unable to reach CRM Pro. Please reload when your connection is restored.';}
