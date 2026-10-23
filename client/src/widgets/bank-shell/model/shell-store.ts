import { makeAutoObservable } from 'mobx';

class ShellStore {
  mobileMenuOpen = false;
  constructor() { makeAutoObservable(this, {}, { autoBind: true }); }
  toggleMobileMenu() { this.mobileMenuOpen = !this.mobileMenuOpen; }
  closeMobileMenu() { this.mobileMenuOpen = false; }
}

export const shellStore = new ShellStore();
