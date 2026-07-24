/** 资料校验工具 — 身份证/银行卡/图片质量 */

/**
 * 身份证号校验（18位）
 * 规则：前17位加权求和，第18位校验码匹配
 */
export function validateIdCard(idCard: string): { valid: boolean; message: string } {
  if (!idCard || !idCard.trim()) {
    return { valid: false, message: '请输入身份证号' }
  }

  const cleaned = idCard.trim().toUpperCase()
  if (!/^\d{17}[\dX]$/.test(cleaned)) {
    return { valid: false, message: '身份证号格式错误，应为18位数字（末位可为X）' }
  }

  // 加权因子
  const weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
  // 校验码映射
  const checkCodes = ['1', '0', 'X', '9', '8', '7', '6', '5', '4', '3', '2']

  let sum = 0
  for (let i = 0; i < 17; i++) {
    sum += parseInt(cleaned[i]) * weights[i]
  }

  const expectedCheck = checkCodes[sum % 11]
  if (cleaned[17] !== expectedCheck) {
    return { valid: false, message: '身份证号校验失败，请核对后重新输入' }
  }

  // 生日合法性校验
  const year = parseInt(cleaned.substring(6, 10))
  const month = parseInt(cleaned.substring(10, 12))
  const day = parseInt(cleaned.substring(12, 14))
  const birth = new Date(year, month - 1, day)
  if (birth.getFullYear() !== year || birth.getMonth() + 1 !== month || birth.getDate() !== day) {
    return { valid: false, message: '身份证号中出生日期无效' }
  }

  return { valid: true, message: 'ok' }
}

/**
 * 银行卡号校验（Luhn 算法）
 */
export function validateBankCard(cardNo: string): { valid: boolean; message: string } {
  if (!cardNo || !cardNo.trim()) {
    return { valid: false, message: '请输入银行卡号' }
  }

  const cleaned = cardNo.trim().replace(/\s/g, '')
  if (!/^\d{8,19}$/.test(cleaned)) {
    return { valid: false, message: '银行卡号格式错误，应为8-19位数字' }
  }

  // Luhn 算法
  let sum = 0
  let alternate = false
  for (let i = cleaned.length - 1; i >= 0; i--) {
    let digit = parseInt(cleaned[i])
    if (alternate) {
      digit *= 2
      if (digit > 9) digit -= 9
    }
    sum += digit
    alternate = !alternate
  }

  if (sum % 10 !== 0) {
    return { valid: false, message: '银行卡号校验失败，请核对后重新输入' }
  }

  return { valid: true, message: 'ok' }
}

/**
 * 图片质量前端检测
 * 检查：模糊度（Laplacian 方差估计）、分辨率、亮度
 */
export async function checkImageQuality(file: File): Promise<{ ok: boolean; warnings: string[] }> {
  const warnings: string[] = []

  if (!file.type.startsWith('image/')) {
    return { ok: true, warnings: [] } // 非图片不检查
  }

  if (file.size < 20000) {
    warnings.push('图片文件过小，可能不清晰，建议重新拍摄')
  }

  try {
    const img = await createImageBitmap(file)
    const { width, height } = img

    if (width < 400 || height < 300) {
      warnings.push(`图片分辨率偏低 (${width}×${height})，建议至少 800×600 的清晰原图`)
    }

    // 使用 Canvas 检测亮度分布
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext('2d')
    if (ctx) {
      ctx.drawImage(img, 0, 0)
      const imageData = ctx.getImageData(0, 0, width, height)
      const pixels = imageData.data

      // 计算平均亮度
      let totalBrightness = 0
      let darkPixels = 0
      for (let i = 0; i < pixels.length; i += 4) {
        const brightness = 0.299 * pixels[i] + 0.587 * pixels[i + 1] + 0.114 * pixels[i + 2]
        totalBrightness += brightness
        if (brightness < 30) darkPixels++  // 过暗像素
      }
      const avgBrightness = totalBrightness / (pixels.length / 4)
      const darkRatio = darkPixels / (pixels.length / 4)

      if (avgBrightness < 50) {
        warnings.push('图片整体过暗，建议在光线充足处重新拍摄')
      } else if (avgBrightness > 220) {
        warnings.push('图片整体过亮，可能存在反光，建议调整角度重新拍摄')
      }

      if (darkRatio > 0.3) {
        warnings.push('图片暗部面积过大，可能存在遮挡或阴影')
      }

      // 估算模糊度：计算相邻像素的亮度差（简化版）
      let edgeSum = 0
      let edgeCount = 0
      for (let y = 0; y < height - 2; y += 3) {
        for (let x = 0; x < width - 2; x += 3) {
          const idx = (y * width + x) * 4
          const b1 = 0.299 * pixels[idx] + 0.587 * pixels[idx + 1] + 0.114 * pixels[idx + 2]
          const idx2 = ((y + 1) * width + x) * 4
          const b2 = 0.299 * pixels[idx2] + 0.587 * pixels[idx2 + 1] + 0.114 * pixels[idx2 + 2]
          edgeSum += Math.abs(b1 - b2)
          edgeCount++
        }
      }
      const avgEdge = edgeSum / edgeCount

      if (avgEdge < 3) {
        warnings.push('图片较为模糊，可能是手抖或对焦不准，建议重新拍摄')
      } else if (avgEdge < 5) {
        warnings.push('图片清晰度一般，建议尽量拍摄清晰原图')
      }
    }

    img.close()
  } catch {
    warnings.push('无法解析图片，请确认文件未损坏')
  }

  return { ok: warnings.length === 0, warnings }
}
