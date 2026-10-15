import { entityPage } from './entities.js';
import { showError } from './ui.js';
entityPage('leads').catch(error=>showError(document.querySelector('main')||document.getElementById('app'),error));
