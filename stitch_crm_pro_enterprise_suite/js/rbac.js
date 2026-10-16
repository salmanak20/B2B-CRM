import {getCurrentUser} from './auth.js';
export const ROLES={OWNER:'owner',ADMIN:'admin',MANAGER:'sales_manager',REP:'sales_rep',VIEWER:'viewer'};
export const getUserRole=()=>getCurrentUser()?.organization_role||getCurrentUser()?.role?.name;
export const isAdmin=()=>[ROLES.OWNER,ROLES.ADMIN].includes(getUserRole());
export const isManagerOrAdmin=()=>[ROLES.OWNER,ROLES.ADMIN,ROLES.MANAGER].includes(getUserRole());
export const canCreateOrEdit=()=>[ROLES.OWNER,ROLES.ADMIN,ROLES.MANAGER,ROLES.REP].includes(getUserRole());
export const canDelete=()=>isManagerOrAdmin();
export const getRoleDisplayName=role=>({owner:'Business Owner',admin:'Administrator',sales_manager:'Sales Manager',sales_rep:'Sales Representative',viewer:'Viewer'})[role]||role;
export function applyRoleUI(){}
