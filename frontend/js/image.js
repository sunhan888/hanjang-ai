// 사진 준비: 휴대폰에서 바로 줄여서 보낸다 (업로드 시간 단축 + HEIC 같은 형식 문제 회피).
// 원본 사진은 휴대폰 메모리에만 있고 서버에는 줄인 JPEG 만 간다.

const MAX_SIDE = 1600;

async function loadImage(file) {
  if ('createImageBitmap' in window) {
    try {
      return await createImageBitmap(file, { imageOrientation: 'from-image' });
    } catch {
      // 일부 브라우저는 옵션을 모른다 → 아래 <img> 방식으로
    }
  }
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('decode')); };
    img.src = url;
  });
}

const sizeOf = (src) => ({ w: src.naturalWidth || src.width, h: src.naturalHeight || src.height });

export async function prepareImage(file, maxSide = MAX_SIDE, quality = 0.85) {
  const src = await loadImage(file);
  const { w, h } = sizeOf(src);
  const scale = Math.min(1, maxSide / Math.max(w, h));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(w * scale);
  canvas.height = Math.round(h * scale);
  canvas.getContext('2d').drawImage(src, 0, 0, canvas.width, canvas.height);
  if (src.close) src.close();
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', quality));
  if (!blob) throw Object.assign(new Error('encode'), { code: 'BAD_IMAGE' });
  return { blob, width: w, height: h };
}

// 확인 화면에 보여 줄 간단한 점검 (모서리·흐림은 서버 판독이 판단한다)
export async function inspectImage(file) {
  const src = await loadImage(file);
  const { w, h } = sizeOf(src);
  const c = document.createElement('canvas');
  c.width = 48;
  c.height = 48;
  const ctx = c.getContext('2d', { willReadFrequently: true });
  ctx.drawImage(src, 0, 0, 48, 48);
  const d = ctx.getImageData(0, 0, 48, 48).data;
  let sum = 0;
  for (let i = 0; i < d.length; i += 4) sum += 0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2];
  if (src.close) src.close();
  const brightness = sum / (d.length / 4);
  const issues = [];
  if (Math.max(w, h) < 1000) issues.push('사진이 작아서 글자가 흐릴 수 있어요.');
  if (brightness < 70) issues.push('사진이 어두워요. 밝은 곳에서 찍으면 더 정확해요.');
  return { width: w, height: h, brightness, issues };
}
