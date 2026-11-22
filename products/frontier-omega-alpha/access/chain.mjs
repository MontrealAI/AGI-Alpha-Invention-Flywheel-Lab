import { ensNormalize, getAddress, hashMessage, id, Interface, namehash, verifyMessage, ZeroAddress } from 'ethers';

// AGI Club names use the Ethereum mainnet ENSv1 Registry and (when wrapped) ENSv1 Name Wrapper.
export const TOKEN = '0xA61a3B3a130a9c20768EEBF97E21515A6046a1fA';
export const MINIMUM = 1_000_000n * 10n ** 18n;
export const REGISTRY = '0x00000000000C2E074eC69A0dFb2997BA6C7d2e1e';
export const WRAPPER = '0xD4416b13d2b3a9aBae7AcD5D6C2BbDBE25686401';
export const REGISTRAR = '0x57f1887a8BF19b14fC0dF6Fd9B2acc9Af147eA85';
export const MAX_CLUB_LABEL_BYTES = 255;
const CLUB_SUFFIX = 'club.agi.eth';
const CLUB_PARENT = namehash(CLUB_SUFFIX);
const CLUB_ROOT = namehash('agi.eth');
const PARENT_CANNOT_CONTROL = 1n << 16n;
const abi = new Interface([
  'function owner(bytes32) view returns (address)',
  'function ownerOf(uint256) view returns (address)',
  'function getData(uint256) view returns (address,uint32,uint64)',
  'function nameExpires(uint256) view returns (uint256)',
  'function GRACE_PERIOD() view returns (uint256)',
  'function decimals() view returns (uint8)',
  'function symbol() view returns (string)',
  'function balanceOf(address) view returns (uint256)',
  'function isValidSignature(bytes32,bytes) view returns (bytes4)'
]);
const bytes = /^0x(?:[0-9a-f]{2})*$/i;
const word = /^0x[0-9a-f]{64}$/i;
const quantity = /^0x(?:0|[1-9a-f][0-9a-f]*)$/i;

export function clubLabel(value) {
  if (typeof value !== 'string' || value.length > MAX_CLUB_LABEL_BYTES) throw Error('Invalid Club label');
  let label;
  try {
    label = ensNormalize(value.trim());
  } catch {
    throw Error('Invalid Club label');
  }
  if (!label || label.includes('.') || new TextEncoder().encode(label).length > MAX_CLUB_LABEL_BYTES) {
    throw Error('Invalid Club label');
  }
  return label;
}

export function clubNode(label) {
  return namehash(clubLabel(label) + '.' + CLUB_SUFFIX);
}

export function httpRpc(endpoint) {
  const url = new URL(endpoint);
  if (url.protocol !== 'https:' || url.username || url.password || url.hash) throw Error('Invalid HTTPS RPC URL');
  return async (method, params) => {
    const res = await fetch(url, {
      method: 'POST',
      redirect: 'error',
      signal: AbortSignal.timeout(6000),
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ jsonrpc: '2.0', id: 1, method, params })
    });
    if (!res.ok) throw Error('RPC unavailable');
    const msg = await res.json();
    if (msg?.jsonrpc !== '2.0' || msg.id !== 1) throw Error('RPC response invalid');
    if (msg.error) {
      // Canonical eth_call execution-reverted code. Other failures remain outages.
      if (method === 'eth_call' && msg.error.code === 3) throw new ContractReverted();
      throw Error('RPC call failed');
    }
    if (!Object.hasOwn(msg, 'result')) throw Error('RPC response missing result');
    return msg.result;
  };
}

class ContractReverted extends Error {}

export class Mainnet {
  #namespaces = new WeakMap();

  constructor(rpc, now = Date.now) {
    this.rpc = rpc;
    this.now = now;
  }

  async snapshot() {
    const [chain, block] = await Promise.all([
      this.rpc('eth_chainId', []),
      this.rpc('eth_getBlockByNumber', ['latest', false])
    ]);
    if (chain !== '0x1' || !word.test(block?.hash) ||
        !quantity.test(block?.number) || !quantity.test(block?.timestamp)) throw Error('Mainnet unavailable');
    const timestamp = Number(BigInt(block.timestamp));
    const age = Math.floor(this.now() / 1000) - timestamp;
    if (age > 90 || age < -12) throw Error('Mainnet head is stale or invalid');
    return {
      ref: { blockHash: block.hash, requireCanonical: true },
      number: BigInt(block.number).toString(),
      timestamp
    };
  }

  async code(address, snapshot) {
    const result = await this.rpc('eth_getCode', [address, snapshot.ref]);
    if (typeof result !== 'string' || !bytes.test(result)) throw Error('Invalid contract bytes');
    return result;
  }

  async call(contract, method, args, snapshot) {
    const data = abi.encodeFunctionData(method, args);
    const result = await this.rpc('eth_call', [{ to: contract, data }, snapshot.ref]);
    const decoded = abi.decodeFunctionResult(method, result);
    if (abi.encodeFunctionResult(method, Array.from(decoded)).toLowerCase() !== result.toLowerCase()) {
      throw Error('Noncanonical contract response');
    }
    return decoded;
  }

  async #ensOwner(node, snapshot) {
    const [registryOwner] = await this.call(REGISTRY, 'owner', [node], snapshot);
    if (registryOwner !== WRAPPER) return { owner: registryOwner, expires: null };
    const [[owner], [recordedOwner, fuses, expiry]] = await Promise.all([
      this.call(WRAPPER, 'ownerOf', [node], snapshot),
      this.call(WRAPPER, 'getData', [node], snapshot)
    ]);
    if (owner !== recordedOwner) return { owner: ZeroAddress, expires: null };
    // Only an emancipated ENSv1 name loses ownership when its wrapper fuses expire.
    return { owner, expires: (fuses & PARENT_CANNOT_CONTROL) ? expiry : null };
  }

  async #clubNamespace(snapshot) {
    if (!this.#namespaces.has(snapshot)) {
      this.#namespaces.set(snapshot, Promise.all([
        this.#ensOwner(CLUB_PARENT, snapshot), this.#ensOwner(CLUB_ROOT, snapshot),
        this.call(REGISTRAR, 'nameExpires', [id('agi')], snapshot),
        this.call(REGISTRAR, 'GRACE_PERIOD', [], snapshot)
      ]));
    }
    return this.#namespaces.get(snapshot);
  }

  async ownsClub(address, label, snapshot) {
    const member = await this.#ensOwner(clubNode(label), snapshot);
    if (member.owner === ZeroAddress || member.owner !== address) return false;
    const [parent, root, [registrationExpiry], [grace]] = await this.#clubNamespace(snapshot);
    const current = BigInt(Math.max(snapshot.timestamp, Math.floor(this.now() / 1000)));
    if (registrationExpiry === 0n || registrationExpiry + grace <= current) return false;
    return [member, parent, root].every(name => name.owner !== ZeroAddress && (name.expires === null || name.expires > current));
  }

  async tokenIdentity(snapshot) {
    const [code, [decimals], [symbol]] = await Promise.all([
      this.code(TOKEN, snapshot),
      this.call(TOKEN, 'decimals', [], snapshot),
      this.call(TOKEN, 'symbol', [], snapshot)
    ]);
    if (code === '0x' || decimals !== 18n || symbol !== 'AGIALPHA') throw Error('Token identity unavailable');
    return { token: TOKEN, decimals: 18, symbol, block: snapshot.number, hash: snapshot.ref.blockHash };
  }

  async ownsToken(address, snapshot) {
    const [, [balance]] = await Promise.all([
      this.tokenIdentity(snapshot),
      this.call(TOKEN, 'balanceOf', [address], snapshot)
    ]);
    return balance >= MINIMUM;
  }

  async entitlement(address, label, snapshot) {
    const paths = label
      ? [['club', this.ownsClub(address, label, snapshot)], ['token', this.ownsToken(address, snapshot)]]
      : [['token', this.ownsToken(address, snapshot)]];
    const results = await Promise.allSettled(paths.map(([, check]) => check));
    const eligible = results.findIndex(result => result.status === 'fulfilled' && result.value);
    if (eligible !== -1) return paths[eligible][0];
    if (results.some(result => result.status === 'rejected')) throw Error('Entitlement unavailable');
    return null;
  }

  async signature(address, message, signature, snapshot, contractRequired = false) {
    const code = await this.code(address, snapshot);
    if (code === '0x') {
      if (contractRequired) return null;
      try {
        return getAddress(verifyMessage(message, signature)) === address ? 'eoa' : null;
      } catch {
        return null;
      }
    }
    try {
      const [magic] = await this.call(address, 'isValidSignature', [hashMessage(message), signature], snapshot);
      return magic === '0x1626ba7e' ? 'contract' : null;
    } catch (error) {
      if (error instanceof ContractReverted) return null;
      throw error;
    }
  }
}
