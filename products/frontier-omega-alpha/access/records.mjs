export const sections = ['radar', 'opportunity', 'experiment', 'verification', 'compounding', 'archive'];
export const validId = value => typeof value === 'string' && /^[a-z0-9][a-z0-9-]{0,79}$/.test(value);
export const validVersion = value => Number.isSafeInteger(value) && value >= 1;
export const maximumAssetBytes = 256 * 1024;

export function validateRecord(record) {
  if (!record || !sections.includes(record.section)) throw Error('Invalid research section');
  for (const lang of ['en', 'fr']) {
    const { title, paragraphs } = record[lang] ?? {};
    if (typeof title !== 'string' || !title.trim() || title.length > 240 ||
        !Array.isArray(paragraphs) || !paragraphs.length ||
        !paragraphs.every(text => typeof text === 'string' && text.trim())) {
      throw Error('Each research release requires a title and paragraphs in both languages');
    }
  }
  if (record.sources !== undefined && (!Array.isArray(record.sources) || record.sources.length > 20 ||
      !record.sources.every(source => {
        const url = new URL(source?.url);
        return ['en', 'fr'].every(lang => typeof source[lang] === 'string' && source[lang].trim() && source[lang].length <= 240) &&
          url.protocol === 'https:' && !url.username && !url.password;
      }))) throw Error('Invalid external source list');
  return record;
}
