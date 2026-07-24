const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // Можно добавить API для связи с main процессом в будущем
});
