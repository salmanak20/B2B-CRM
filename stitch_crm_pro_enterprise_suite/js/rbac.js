import {getCurrentUser} from './auth.js';
export const ROLES={ADMIN:'admin',MANAGER:'sales_manager',REP:'sales_rep',VIEWER:'viewer'};
export const getUserRole=()=>getCurrentUser()?.role?.name;
export const isAdmin=()=>getUserRole()===ROLES.ADMIN;
export const isManagerOrAdmin=()=>[ROLES.ADMIN,ROLES.MANAGER].includes(getUserRole());
export const canCreateOrEdit=()=>[ROLES.ADMIN,ROLES.MANAGER,ROLES.REP].includes(getUserRole());
export const canDelete=()=>isManagerOrAdmin();
export const getRoleDisplayName=role=>({admin:'Administrator',sales_manager:'Sales Manager',sales_rep:'Sales Representative',viewer:'Viewer'})[role]||role;
export function applyRoleUI(){}
