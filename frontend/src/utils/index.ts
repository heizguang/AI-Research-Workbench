/**
 * 工具函数模块
 */

/**
 * 格式化日期
 */
export const formatDate = (date: string | Date): string => {
  const d = new Date(date);
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

/**
 * 格式化文件大小
 */
export const formatFileSize = (bytes: number): string => {
  const units = ['B', 'KB', 'MB', 'GB'];
  let size = bytes;
  let unitIndex = 0;

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }

  return `${size.toFixed(2)} ${units[unitIndex]}`;
};

/**
 * 截断文本
 */
export const truncateText = (text: string, maxLength: number = 100): string => {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + '...';
};

/**
 * 生成唯一ID
 */
export const generateId = (): string => {
  return Math.random().toString(36).substring(2) + Date.now().toString(36);
};

/**
 * 防抖函数
 */
export const debounce = <T extends (...args: any[]) => any>(
  func: T,
  wait: number
): ((...args: Parameters<T>) => void) => {
  let timeout: NodeJS.Timeout;

  return (...args: Parameters<T>) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
};

/**
 * 节流函数
 */
export const throttle = <T extends (...args: any[]) => any>(
  func: T,
  limit: number
): ((...args: Parameters<T>) => void) => {
  let inThrottle: boolean;

  return (...args: Parameters<T>) => {
    if (!inThrottle) {
      func(...args);
      inThrottle = true;
      setTimeout(() => (inThrottle = false), limit);
    }
  };
};

/**
 * 复制到剪贴板
 */
export const copyToClipboard = async (text: string): Promise<boolean> => {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (err) {
    console.error('Failed to copy:', err);
    return false;
  }
};

/**
 * 下载文件
 */
export const downloadFile = (url: string, filename: string): void => {
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};

/**
 * 验证邮箱格式
 */
export const isValidEmail = (email: string): boolean => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
};

/**
 * 验证URL格式
 */
export const isValidUrl = (url: string): boolean => {
  try {
    new URL(url);
    return true;
  } catch {
    return false;
  }
};

/**
 * 获取文件扩展名
 */
export const getFileExtension = (filename: string): string => {
  return filename.slice(((filename.lastIndexOf('.') - 1) >>> 0) + 2);
};

/**
 * 检查是否为移动设备
 */
export const isMobile = (): boolean => {
  return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(
    navigator.userAgent
  );
};

/**
 * 获取随机颜色
 */
export const getRandomColor = (): string => {
  const letters = '0123456789ABCDEF';
  let color = '#';
  for (let i = 0; i < 6; i++) {
    color += letters[Math.floor(Math.random() * 16)];
  }
  return color;
};

/**
 * 深拷贝对象
 */
export const deepClone = <T>(obj: T): T => {
  return JSON.parse(JSON.stringify(obj));
};

/**
 * 清理 Markdown 格式，转为纯文本
 * 用于导入历史报告到 Q&A / PPT 时去除格式符号
 */
export const stripMarkdown = (text: string): string => {
  let s = text;
  // 去掉标题符号 (# ## ### 等)
  s = s.replace(/^#{1,6}\s+/gm, '');
  // 去掉加粗 **text** 或 __text__
  s = s.replace(/\*\*(.+?)\*\*/g, '$1');
  s = s.replace(/__(.+?)__/g, '$1');
  // 去掉斜体 *text* 或 _text_（但不误伤列表符号 *   ）
  s = s.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, '$1');
  s = s.replace(/(?<!_)_(?!_)(.+?)(?<!_)_(?!_)/g, '$1');
  // 去掉行内代码 `text`
  s = s.replace(/`(.+?)`/g, '$1');
  // 去掉链接 [text](url) 只保留文字
  s = s.replace(/\[(.+?)\]\(.+?\)/g, '$1');
  // 去掉来源标注 [来源 X][来源 Y] 等
  s = s.replace(/\[来源\s*\d+\]/g, '');
  s = s.replace(/【来源[:：].*?】/g, '');
  // 去掉删除线 ~~text~~
  s = s.replace(/~~(.+?)~~/g, '$1');
  // 去掉水平分隔线 --- 或 ***
  s = s.replace(/^\s*[-*]{3,}\s*$/gm, '');
  // 去掉图片 ![alt](url)
  s = s.replace(/!\[(.+?)\]\(.+?\)/g, '$1');
  // 去掉引用块 > text
  s = s.replace(/^>\s*/gm, '');
  // 合并多余空行
  s = s.replace(/\n{3,}/g, '\n\n');
  // 去掉行首多余空格
  s = s.replace(/^\s{2,}/gm, '');
  return s.trim();
};

/**
 * 延迟执行
 */
export const sleep = (ms: number): Promise<void> => {
  return new Promise((resolve) => setTimeout(resolve, ms));
};

/**
 * 生成 UUID v4
 * 优先使用 crypto.randomUUID()（需安全上下文），
 * 回退到 crypto.getRandomValues()，最终回退到 Math.random()
 */
export const generateUUID = (): string => {
  // 方法一：crypto.randomUUID()（HTTPS / localhost）
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  // 方法二：crypto.getRandomValues()（兼容性更广）
  if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
    const arr = new Uint8Array(16);
    crypto.getRandomValues(arr);
    // 设置 UUID v4 版本位 (4) 和变体位 (10xx)
    arr[6] = (arr[6] & 0x0f) | 0x40;
    arr[8] = (arr[8] & 0x3f) | 0x80;
    const hex = Array.from(arr, (b) => b.toString(16).padStart(2, '0'));
    return [
      hex[0], hex[1], hex[2], hex[3], '-',
      hex[4], hex[5], '-',
      hex[6], hex[7], '-',
      hex[8], hex[9], '-',
      hex[10], hex[11], hex[12], hex[13], hex[14], hex[15],
    ].join('');
  }
  // 方法三：Math.random() 最终回退
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
};

/**
 * 字符串哈希（生成确定性 ID，用于替代 crypto.subtle.digest('SHA-256')）
 * 优先使用 crypto.subtle.digest（需安全上下文），回退到 FNV-1a 多重哈希
 * 返回 64 位十六进制字符串，与 SHA-256 输出格式一致
 */
export const hashString = async (str: string): Promise<string> => {
  // 方法一：crypto.subtle.digest('SHA-256')（HTTPS / localhost）
  if (
    typeof crypto !== 'undefined' &&
    typeof crypto.subtle !== 'undefined' &&
    typeof crypto.subtle.digest === 'function'
  ) {
    try {
      const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(str));
      return Array.from(new Uint8Array(buf))
        .map((b) => b.toString(16).padStart(2, '0'))
        .join('');
    } catch {
      // 回退到 JS 实现
    }
  }
  // 方法二：FNV-1a 多重哈希（使用 8 个不同种子生成 256-bit 等效输出）
  const seeds = [
    0x811c9dc5, 0x01000193, 0x85c8c7e3, 0x24b8b1a5,
    0xc6b5a5e3, 0xafb1b7e4, 0x82b7e3a2, 0x22c3c3b4,
  ];
  const hashes = seeds.map((seed) => {
    let h = seed;
    for (let i = 0; i < str.length; i++) {
      h = ((h ^ str.charCodeAt(i)) * 16777619) >>> 0;
    }
    return h;
  });
  return hashes.map((h) => h.toString(16).padStart(8, '0')).join('');
};
