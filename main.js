const { app, BrowserWindow, Tray, Menu, nativeImage } = require('electron');
const path = require('path');

// Попытка загрузить uiohook-napi (может не сработать при первом запуске без npm install)
let uIOhook = null;
try {
  uIOhook = require('uiohook-napi');
} catch (e) {
  console.warn('uiohook-napi не установлен. Глобальный хук NumLock не будет работать. Выполните npm install.');
}

let mainWindow = null;
let tray = null;
let isQuitting = false;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 480,
    height: 680,
    minWidth: 380,
    minHeight: 550,
    frame: true,
    resizable: true,
    show: false,
    icon: path.join(__dirname, 'assets', 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));

  mainWindow.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function createTray() {
  // Для portable-версии ищем иконку рядом с exe или в assets
  const trayIconPath = path.join(__dirname, 'assets', 'tray-icon.png');
  const trayIcon = nativeImage.createFromPath(trayIconPath);
  tray = new Tray(trayIcon.resize({ width: 16, height: 16 }));

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Показать / Скрыть',
      click: () => toggleWindow(),
    },
    { type: 'separator' },
    {
      label: 'Автозапуск',
      type: 'checkbox',
      checked: app.getLoginItemSettings().openAtLogin,
      click: (menuItem) => {
        app.setLoginItemSettings({ openAtLogin: menuItem.checked });
      },
    },
    { type: 'separator' },
    {
      label: 'Выход',
      click: () => {
        isQuitting = true;
        app.quit();
      },
    },
  ]);

  tray.setToolTip('NumLock Calc');
  tray.setContextMenu(contextMenu);

  tray.on('click', () => {
    toggleWindow();
  });
}

function toggleWindow() {
  if (!mainWindow) return;
  if (mainWindow.isVisible()) {
    mainWindow.hide();
  } else {
    mainWindow.show();
    mainWindow.focus();
  }
}

function setupNumLockHook() {
  if (!uIOhook) return;

  try {
    uIOhook.on('keydown', (event) => {
      // Код клавиши NumLock = 69 (по данным uiohook)
      if (event.keycode === 69) {
        toggleWindow();
      }
    });

    uIOhook.start();
    console.log('Глобальный хук NumLock активирован');
  } catch (err) {
    console.error('Ошибка запуска uiohook:', err);
  }
}

app.whenReady().then(() => {
  createWindow();
  createTray();
  setupNumLockHook();

  app.on('activate', () => {
    if (mainWindow === null) createWindow();
  });
});

app.on('window-all-closed', () => {
  // Не выходим — приложение живёт в трее
});

app.on('before-quit', () => {
  isQuitting = true;
  if (uIOhook) {
    try { uIOhook.stop(); } catch (e) {}
  }
});
