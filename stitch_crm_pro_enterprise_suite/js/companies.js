import { entityPage } from './entities.js';
import { showError } from './ui.js';
entityPage('companies').catch(error=>showError(document.querySelector('main')||document.getElementById('app'),error));
