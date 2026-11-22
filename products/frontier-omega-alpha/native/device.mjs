const namespace = 'frontier-omega-alpha-native-v1';

export function openDevices() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(namespace, 1);
    request.onupgradeneeded = () => request.result.createObjectStore('devices');
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(Error('storage'));
    request.onblocked = () => reject(Error('storage'));
  });
}

async function useStore(mode, operation) {
  const database = await openDevices();
  try {
    return await new Promise((resolve, reject) => {
      const txn = database.transaction('devices', mode);
      const request = operation(txn.objectStore('devices'));
      txn.oncomplete = () => resolve(request.result);
      txn.onabort = () => reject(Error('storage'));
      txn.onerror = () => reject(Error('storage'));
    });
  } finally {
    database.close();
  }
}

export const loadDevice = wallet => useStore('readonly', store => store.get(wallet));
export function compareDevice(wallet, expected, value) {
  return useStore('readwrite', store => {
    let written = false;
    const read = store.get(wallet);
    read.onsuccess = () => {
      const prior = read.result;
      if (prior?.nonce === expected?.nonce && prior?.phase === expected?.phase && prior?.tx === expected?.tx) {
        store.put(value, wallet);
        written = true;
      }
    };
    return { get result() { return written; } };
  });
}
