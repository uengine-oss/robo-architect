import BaseRenderer from 'diagram-js/lib/draw/BaseRenderer';

import { append as svgAppend, attr as svgAttr, create as svgCreate, remove as svgRemove } from 'tiny-svg';

import { getRoundRectPath } from 'bpmn-js/lib/draw/BpmnRenderUtil';

import { is } from 'bpmn-js/lib/util/ModelUtil';
import { isAny } from 'bpmn-js/lib/features/modeling/util/ModelingUtil';

const HIGH_PRIORITY = 1500,
    TASK_BORDER_RADIUS = 10,
    COLOR_RULES_STORAGE_KEY = 'bpmn_color_rules';

// Check if text contains Korean characters
function containsKorean(text) {
    return /[\uAC00-\uD7A3\u1100-\u11FF\u3130-\u318F]/.test(text);
}

// Estimate text width more accurately
function estimateTextWidth(text, fontSize = 12) {
    if (!text) return 0;

    let width = 0;
    for (let i = 0; i < text.length; i++) {
        const char = text.charAt(i);
        // Korean characters are typically full-width
        if (/[\uAC00-\uD7A3\u1100-\u11FF\u3130-\u318F]/.test(char)) {
            width += fontSize * 1.0; // Full-width for Korean
        } else if (/[a-zA-Z0-9]/.test(char)) {
            width += fontSize * 0.55; // Narrower for alphanumeric
        } else if (char === ' ') {
            width += fontSize * 0.3; // Space
        } else {
            width += fontSize * 0.6; // Default for other characters
        }
    }
    return width;
}

// Text wrapping helper function with better Korean support
function wrapText(text, maxWidth, fontSize = 12) {
    if (!text) return [];

    // Handle explicit newlines (\n)
    const paragraphs = text.split('\n');
    const lines = [];

    paragraphs.forEach((paragraph) => {
        if (!paragraph.trim()) {
            lines.push('');
            return;
        }

        // Check if paragraph fits in one line
        if (estimateTextWidth(paragraph, fontSize) <= maxWidth) {
            lines.push(paragraph);
            return;
        }

        // For Korean text, we can break at any character
        // For English/mixed text, we prefer word boundaries
        if (containsKorean(paragraph)) {
            // Character-by-character wrapping for Korean
            let currentLine = '';
            for (let i = 0; i < paragraph.length; i++) {
                const char = paragraph.charAt(i);
                const testLine = currentLine + char;

                if (estimateTextWidth(testLine, fontSize) <= maxWidth) {
                    currentLine = testLine;
                } else {
                    if (currentLine) {
                        lines.push(currentLine);
                    }
                    currentLine = char;
                }
            }
            if (currentLine) {
                lines.push(currentLine);
            }
        } else {
            // Word wrap for non-Korean text
            const words = paragraph.split(/(\s+)/);
            let currentLine = '';

            words.forEach((word) => {
                if (!word) return;

                const testLine = currentLine + word;
                if (estimateTextWidth(testLine, fontSize) <= maxWidth) {
                    currentLine = testLine;
                } else {
                    if (currentLine.trim()) {
                        lines.push(currentLine.trim());
                    }
                    currentLine = word.trim() ? word : '';
                }
            });

            if (currentLine.trim()) {
                lines.push(currentLine.trim());
            }
        }
    });

    return lines;
}

// Render wrapped text as SVG text element with tspans
function renderWrappedText(parentNode, text, x, y, width, height, fontSize, fillColor) {
    const lines = wrapText(text, width - 20, fontSize); // 20px padding for better margin
    if (lines.length === 0) return null;

    const lineHeight = fontSize * 1.4; // Slightly more line height for better readability
    const totalTextHeight = lines.length * lineHeight;

    // Center text vertically, with adjustment for better visual centering
    const startY = y + (height - totalTextHeight) / 2 + fontSize * 0.8;

    const textElement = svgCreate('text');
    svgAttr(textElement, {
        class: 'custom-wrapped-text',
        'text-anchor': 'middle',
        'font-size': fontSize + 'px',
        'font-family': 'Arial, sans-serif',
        fill: fillColor || '#000000',
        'pointer-events': 'none'
    });

    lines.forEach((line, index) => {
        const tspan = svgCreate('tspan');
        svgAttr(tspan, {
            x: x + width / 2,
            y: startY + index * lineHeight,
            'dominant-baseline': 'middle'
        });
        tspan.textContent = line;
        svgAppend(textElement, tspan);
    });

    svgAppend(parentNode, textElement);
    return textElement;
}

// Convert HEX to RGB
function hexToRgb(hex) {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result
        ? {
              r: parseInt(result[1], 16),
              g: parseInt(result[2], 16),
              b: parseInt(result[3], 16)
          }
        : { r: 0, g: 0, b: 0 };
}

// Convert RGB to HEX
function rgbToHex(r, g, b) {
    return (
        '#' +
        [r, g, b]
            .map((x) => {
                const hex = Math.round(Math.max(0, Math.min(255, x))).toString(16);
                return hex.length === 1 ? '0' + hex : hex;
            })
            .join('')
    );
}

// Convert sRGB to linear RGB
function srgbToLinear(c) {
    c = c / 255;
    return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}

// Convert linear RGB to sRGB
function linearToSrgb(c) {
    return c <= 0.0031308 ? c * 12.92 * 255 : (1.055 * Math.pow(c, 1 / 2.4) - 0.055) * 255;
}

// Convert RGB to OKLAB
function rgbToOklab(r, g, b) {
    const lr = srgbToLinear(r);
    const lg = srgbToLinear(g);
    const lb = srgbToLinear(b);

    const l = 0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb;
    const m = 0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb;
    const s = 0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb;

    const l_ = Math.cbrt(l);
    const m_ = Math.cbrt(m);
    const s_ = Math.cbrt(s);

    return {
        L: 0.2104542553 * l_ + 0.793617785 * m_ - 0.0040720468 * s_,
        a: 1.9779984951 * l_ - 2.428592205 * m_ + 0.4505937099 * s_,
        b: 0.0259040371 * l_ + 0.7827717662 * m_ - 0.808675766 * s_
    };
}

// Convert OKLAB to RGB
function oklabToRgb(L, a, b) {
    const l_ = L + 0.3963377774 * a + 0.2158037573 * b;
    const m_ = L - 0.1055613458 * a - 0.0638541728 * b;
    const s_ = L - 0.0894841775 * a - 1.291485548 * b;

    const l = l_ * l_ * l_;
    const m = m_ * m_ * m_;
    const s = s_ * s_ * s_;

    const lr = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s;
    const lg = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s;
    const lb = -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s;

    return {
        r: linearToSrgb(lr),
        g: linearToSrgb(lg),
        b: linearToSrgb(lb)
    };
}

// Interpolate color using OKLAB color space for perceptually uniform transitions
function interpolateColorOklab(startHex, endHex, ratio) {
    const start = hexToRgb(startHex);
    const end = hexToRgb(endHex);

    const startLab = rgbToOklab(start.r, start.g, start.b);
    const endLab = rgbToOklab(end.r, end.g, end.b);

    // Linear interpolation in OKLAB space
    const L = startLab.L + (endLab.L - startLab.L) * ratio;
    const a = startLab.a + (endLab.a - startLab.a) * ratio;
    const b = startLab.b + (endLab.b - startLab.b) * ratio;

    const rgb = oklabToRgb(L, a, b);
    return rgbToHex(rgb.r, rgb.g, rgb.b);
}

// Adjust color intensity (lightness) based on ratio
// ratio 0 = original/light, ratio 1 = darker
function adjustColorIntensity(hexColor, ratio) {
    const rgb = hexToRgb(hexColor);
    const lab = rgbToOklab(rgb.r, rgb.g, rgb.b);

    // Adjust lightness: lighter when ratio is low, darker when ratio is high
    // Original lightness is maintained at ratio=0, reduced to ~40% at ratio=1
    const minLightness = 0.35; // Minimum lightness (darkest)
    const maxLightness = Math.min(lab.L * 1.15, 0.95); // Slightly lighter than original, capped at 0.95

    // Linear interpolation from maxLightness to minLightness
    const newL = maxLightness - (maxLightness - minLightness) * ratio;

    // Keep hue and saturation (a, b), only adjust lightness
    const newRgb = oklabToRgb(newL, lab.a, lab.b);
    return rgbToHex(newRgb.r, newRgb.g, newRgb.b);
}

// Calculate relative luminance (WCAG formula)
// Returns value between 0 (black) and 1 (white)
function getRelativeLuminance(hexColor) {
    const rgb = hexToRgb(hexColor);

    // Convert to sRGB
    const rsRGB = rgb.r / 255;
    const gsRGB = rgb.g / 255;
    const bsRGB = rgb.b / 255;

    // Apply gamma correction
    const r = rsRGB <= 0.03928 ? rsRGB / 12.92 : Math.pow((rsRGB + 0.055) / 1.055, 2.4);
    const g = gsRGB <= 0.03928 ? gsRGB / 12.92 : Math.pow((gsRGB + 0.055) / 1.055, 2.4);
    const b = bsRGB <= 0.03928 ? bsRGB / 12.92 : Math.pow((bsRGB + 0.055) / 1.055, 2.4);

    // Calculate luminance
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

// Check if background is dark enough to need white text
// Using WCAG contrast ratio threshold
function shouldUseWhiteText(hexColor) {
    const luminance = getRelativeLuminance(hexColor);
    // If luminance is below 0.4, use white text for better contrast
    return luminance < 0.4;
}

// Get color from rules stored in BPMN XML (via window.$bpmnColorRules)
function getColorFromRules(element) {
    try {
        const rules = window.$bpmnColorRules;
        if (!rules || !Array.isArray(rules) || rules.length === 0) {
            return null;
        }

        const defaultColor = '#fdf2d0';

        // Get element type
        const elementType = element.businessObject?.$type;
        if (!elementType) return { fillColor: defaultColor };

        // Get leadTime (duration) from extension elements
        let leadTime = null;
        const extensionElements = element.businessObject?.extensionElements;
        if (extensionElements?.values) {
            const uengineProps = extensionElements.values.find((v) => v.$type === 'uengine:Properties');
            if (uengineProps?.json) {
                try {
                    const parsed = JSON.parse(uengineProps.json);
                    // Support both 'duration' and 'leadTime' property names
                    if (parsed.leadTime !== undefined) {
                        leadTime = Number(parsed.leadTime);
                    } else if (parsed.duration !== undefined) {
                        leadTime = Number(parsed.duration);
                    }
                } catch (e) {
                    // Ignore parse errors
                }
            }
        }

        // Sort rules by priority
        const sortedRules = [...rules].filter((r) => r.enabled).sort((a, b) => (a.priority || 0) - (b.priority || 0));

        // Step 1: Get base color from task type rules
        let baseColor = defaultColor;
        let baseStrokeColor = '';
        for (const rule of sortedRules.filter((r) => r.type === 'taskType')) {
            if (rule.taskTypes?.includes(elementType)) {
                baseColor = rule.fillColor || defaultColor;
                baseStrokeColor = rule.strokeColor || '';
                break;
            }
        }

        // Step 2: Apply leadTime intensity adjustment if applicable
        if (leadTime !== null) {
            for (const rule of sortedRules.filter((r) => r.type === 'leadTime')) {
                const min = rule.minDuration ?? 0;
                const max = rule.maxDuration ?? 60;

                if (leadTime >= min && leadTime <= max) {
                    // Calculate ratio: 0 = short time (light), 1 = long time (dark)
                    const range = max - min;
                    const ratio = range > 0 ? Math.min(1, Math.max(0, (leadTime - min) / range)) : 0;

                    // Apply intensity adjustment to base color
                    const adjustedColor = adjustColorIntensity(baseColor, ratio);
                    return { fillColor: adjustedColor, strokeColor: baseStrokeColor };
                }
            }
        }

        // Return base color if no leadTime rule matched
        if (baseColor !== defaultColor) {
            return { fillColor: baseColor, strokeColor: baseStrokeColor };
        }

        return null;
    } catch (e) {
        console.warn('Failed to get color from rules:', e);
        return null;
    }
}

export default class CustomBpmnRenderer extends BaseRenderer {
    constructor(eventBus, bpmnRenderer, canvas, options, elementRegistry, graphicsFactory) {
        super(eventBus, HIGH_PRIORITY);
        this.bpmnRenderer = bpmnRenderer;
        this.canvas = canvas; // canvas를 직접 저장합니다.
        this.elementRegistry = elementRegistry;
        this.graphicsFactory = graphicsFactory;

        // 'canvas.init' 이벤트에 리스너를 등록합니다.
        eventBus.on('canvas.init', () => {
            this.addTitleToDiagram(this.canvas); // canvas를 addTitleToDiagram에 전달합니다.
        });
    }

    addTitleToDiagram(canvas) {
        // SVG 루트 요소를 가져옵니다.
        const svgRoot = canvas._svg;

        // 새로운 text SVG 요소를 생성합니다.
        const titleText = svgCreate('text');
        svgAttr(titleText, {
            x: '110',
            y: '110',
            'font-size': '24px',
            'font-family': 'Arial, sans-serif',
            'font-weight': '700',
            'text-anchor': 'middle',
            fill: '#535353'
        });
        // titleText.textContent = '영업 활동 프로세스';

        svgAppend(svgRoot, titleText);
    }

    canRender(element) {
        // only render tasks and events (ignore labels)
        return (
            isAny(element, [
                'bpmn:Task',
                'bpmn:Lane',
                'bpmn:Participant',
                'bpmn:SequenceFlow',
                'bpmn:StartEvent',
                'bpmn:EndEvent',
                'bpmn2:outgoing',
                'label',
                'bpmn:Gateway',
                'bpmn:SubProcess',
                'bpmn:CallActivity',
                'phase:Phase'
            ]) && !element.labelTarget
        );
    }

    registerCustomHandlers() {
        if (!this.bpmnRenderer.handlers) {
            console.warn('BpmnRenderer에 handlers 속성이 존재하지 않음');
            return;
        }

        const originalDrawLane = this.bpmnRenderer.handlers['bpmn:Lane'];

        this.bpmnRenderer.handlers['phase:Phase'] = (parentNode, element) => {
            return originalDrawLane(parentNode, element);
        };

        this.bpmnRenderer.handlers['phase:PhaseContainer'] = (parentNode, element) => {
            return originalDrawLane(parentNode, element);
        };

        // this.bpmnRenderer.handlers["phase:Phase"] = (parentNode, element) => {
        //   return this.drawCustomPhase(parentNode, element);
        // };
    }

    drawShape(parentNode, element) {
        // console.log('Rendering a Task:', parentNode, element);
        this.registerCustomHandlers();
        const shape = this.bpmnRenderer.drawShape(parentNode, element);
        // 각 요소별로 분리한 함수를 호출합니다.

        if (is(element, 'bpmn:Task')) {
            // 라벨을 찾아서 모든 'tspan' 요소에 대해 스타일을 변경합니다.
            this.drawCustomTask(parentNode, shape, element);
            // const tspanElements = parentNode.querySelectorAll('text.djs-label tspan');
            // tspanElements.forEach((tspan) => {
            //   svgAttr(tspan, { fill: 'red' }); // 모든 tspan 요소에 red 색상을 적용합니다.
            // });
        } else if (is(element, 'bpmn:StartEvent')) {
            this.drawCustomStartEvent(parentNode, shape, element);
        } else if (is(element, 'bpmn:EndEvent')) {
            this.drawCustomEndEvent(parentNode, shape, element);
        } else if (is(element, 'phase:PhaseContainer')) {
            this.drawCustomPhaseContainer(parentNode, shape, element);
        } else if (is(element, 'phase:Phase')) {
            this.drawCustomPhase(parentNode, shape, element);
        } else if (is(element, 'bpmn:Lane')) {
            this.drawCustomLane(parentNode, shape, element);
        } else if (is(element, 'bpmn:Participant')) {
            this.drawCustomParticipant(parentNode, shape, element);
        } else if (is(element, 'label')) {
            this.drawCustomLabel(parentNode, shape, element);
        } else if (is(element, 'bpmn:Gateway')) {
            this.drawCustomGateway(parentNode, shape, element);
        } else if (is(element, 'bpmn:SequenceFlow')) {
            this.drawConnection(parentNode, element);
        } else if (is(element, 'bpmn:SubProcess') || is(element, 'bpmn:CallActivity')) {
            this.drawCustomSubProcess(parentNode, shape, element);
        }

        return shape;
    }

    // 스윔레인 배경 색상 및 선 색상 bpmn:Lane, (stroke : 선 색상, fill: 배경 색상)
    drawCustomLane(parentNode, shape, element) {
        svgAttr(shape, {
            stroke: '#4e72be',
            strokeWidth: '1',
            fill: '#f4f8fc'
        });
    }

    drawCustomParticipant(parentNode, shape, element) {
        svgAttr(shape, {
            stroke: '#4e72be',
            fill: '#f4f8fc'
        });
    }

    // No-op: external labels are excluded by canRender (!element.labelTarget),
    // so this branch is effectively unreachable — defined only as a safety net.
    drawCustomLabel(parentNode, shape) {
        return shape;
    }

    drawCustomPhase(parentNode, shape, element) {
        const existingWidth = shape.width.baseVal.value;
        const existingHeight = shape.height.baseVal.value;
        const isVertical = existingHeight > existingWidth;

        const fillColor = element.businessObject.fillColor || '#f4f8fc';
        const strokeColor = element.businessObject.strokeColor || '#4e72be';

        const phaseVisual = drawNotchTag(parentNode, existingWidth, existingHeight, fillColor, strokeColor, 0, 0, isVertical);

        const text = parentNode.children[1];
        if (isVertical) {
            const centerX = existingWidth / 2;
            const centerY = existingHeight / 2;
            svgAttr(text, {
                x: centerX,
                y: centerY,
                'text-anchor': 'middle',
                'alignment-baseline': 'middle',
                'font-size': '14px',
                'font-family': 'Arial, sans-serif',
                fill: '#333',
                'font-weight': 'bold',
                transform: `rotate(-90, ${centerX}, ${centerY})`
            });
        } else {
            svgAttr(text, {
                x: existingWidth / 2,
                y: existingHeight - 30,
                'text-anchor': 'middle',
                'alignment-baseline': 'middle',
                'font-size': '20px',
                'font-family': 'Arial, sans-serif',
                fill: '#333',
                'font-weight': 'bold'
            });
        }
        text.textContent = element.businessObject.name;

        prependTo(phaseVisual, parentNode);
        svgRemove(shape);
    }

    drawCustomPhaseContainer(parentNode, shape, element) {
        svgRemove(shape);
    }

    // bpmn:UserTask 관련
    drawCustomTask(parentNode, shape, element) {
        // 기존 shape의 크기를 가져옵니다.
        const existingWidth = shape.width.baseVal.value;
        const existingHeight = shape.height.baseVal.value;

        var strokeColor = 'none';

        // Priority 1: Check for individual task color in extension elements
        let fillColor = null;
        let customStrokeColor = 'none';
        let hasIndividualColor = false;

        let systemName = '';
        let menuName = '';

        const extensionElements = element.businessObject?.extensionElements;
        if (extensionElements && extensionElements.values) {
            const uengineProps = extensionElements.values.find((v) => v.$type === 'uengine:Properties');
            if (uengineProps && uengineProps.json) {
                try {
                    const props = JSON.parse(uengineProps.json);
                    if (props.taskColor) {
                        fillColor = props.taskColor;
                        hasIndividualColor = true;
                    }
                    if (props.taskStrokeColor) {
                        customStrokeColor = props.taskStrokeColor;
                    }
                    if (props.systemName) {
                        systemName = props.systemName;
                    }
                    if (props.menuName) {
                        menuName = props.menuName;
                    }
                } catch (e) {
                    // Ignore JSON parse errors
                }
            }
        }

        // Also check direct businessObject properties as fallback for individual color
        if (element.businessObject?.fillColor) {
            fillColor = element.businessObject.fillColor;
            hasIndividualColor = true;
        }
        if (element.businessObject?.strokeColor) {
            customStrokeColor = element.businessObject.strokeColor;
        }

        // Priority 2: If no individual color, apply color rules
        if (!hasIndividualColor) {
            const ruleColor = getColorFromRules(element);
            if (ruleColor) {
                fillColor = ruleColor.fillColor;
                if (ruleColor.strokeColor) {
                    customStrokeColor = ruleColor.strokeColor;
                }
            }
        }

        // Priority 3: Fallback to default color
        if (!fillColor) {
            fillColor = '#fdf2d0';
        }

        const borderRect = drawBorderRect(parentNode, existingWidth, existingHeight, TASK_BORDER_RADIUS, customStrokeColor);
        prependTo(borderRect, parentNode);
        const rect = drawRect(parentNode, existingWidth, existingHeight, TASK_BORDER_RADIUS, 'none', fillColor, shape.style);
        prependTo(rect, parentNode);
        svgRemove(shape);

        // Dynamic text color: white text on dark backgrounds
        const useWhiteText = shouldUseWhiteText(fillColor);
        const textColor = useWhiteText ? '#ffffff' : '#000000';

        // Set data attribute for CSS-based styling (immediate, no flicker)
        if (parentNode.closest) {
            const container = parentNode.closest('.djs-element');
            if (container) {
                container.setAttribute('data-dark-bg', useWhiteText ? 'true' : 'false');
            }
        }

        // Get task name for text wrapping
        const taskName = element.businessObject?.name || '';

        // Remove ALL existing text elements (including djs-label and any other text)
        // This ensures our wrapped text is the only text rendered
        const existingTexts = parentNode.querySelectorAll('text:not(.custom-wrapped-text)');
        existingTexts.forEach((textEl) => {
            try {
                svgRemove(textEl);
            } catch (e) {
                // Ignore if already removed
            }
        });

        // Also remove any previously added custom wrapped text
        const previousCustomText = parentNode.querySelectorAll('text.custom-wrapped-text');
        previousCustomText.forEach((textEl) => {
            try {
                svgRemove(textEl);
            } catch (e) {
                // Ignore if already removed
            }
        });

        // Render wrapped text with line breaks support
        if (taskName) {
            const fontSize = 12;
            renderWrappedText(parentNode, taskName, 0, 0, existingWidth, existingHeight, fontSize, textColor);
        }

        // Apply text color to any remaining text elements (safety check)
        const textElements = parentNode.querySelectorAll('text, text tspan');
        textElements.forEach((textEl) => {
            svgAttr(textEl, { fill: textColor });
        });

        // Use MutationObserver to handle text elements added after our rendering
        // But skip if directEditing is active (인라인 편집 중에는 텍스트 제거하지 않음)
        const observer = new MutationObserver((mutations) => {
            // Check if directEditing is active by looking for djs-direct-editing-parent class
            const isDirectEditing = document.querySelector('.djs-direct-editing-parent');
            if (isDirectEditing) {
                return; // Skip removal during direct editing
            }

            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeName === 'text' && !node.classList.contains('custom-wrapped-text')) {
                        // Remove default text added by BPMN-JS
                        try {
                            svgRemove(node);
                        } catch (e) {
                            // Ignore
                        }
                    }
                });
            });
        });

        observer.observe(parentNode, { childList: true, subtree: true });

        // Disconnect observer after a short delay (BPMN-JS should have finished rendering)
        setTimeout(() => {
            observer.disconnect();
        }, 100);

        // Phase 4-2: Display Business ID label above the Task
        const extensionElements2 = element.businessObject?.extensionElements;
        let businessId = '';
        if (extensionElements2 && extensionElements2.values) {
            const uengineProps2 = extensionElements2.values.find((v) => v.$type === 'uengine:Properties');
            if (uengineProps2 && uengineProps2.json) {
                try {
                    const props2 = JSON.parse(uengineProps2.json);
                    if (props2.businessId) businessId = props2.businessId;
                } catch (e) {
                    /* ignore */
                }
            }
        }
        if (businessId) {
            const bidLabel = svgCreate('text');
            svgAttr(bidLabel, {
                x: existingWidth / 2,
                y: -6,
                'text-anchor': 'middle',
                'font-size': '9px',
                'font-family': '"Courier New", monospace',
                fill: '#888888',
                'pointer-events': 'none'
            });
            bidLabel.textContent = businessId;
            svgAppend(parentNode, bidLabel);
        }

        // Phase 4-3: Time-Travel Visual Cues
        const timeTravel = window.$bpmnTimeTravel;
        if (timeTravel === 'toBe') {
            let futureStatus = '';
            if (extensionElements2 && extensionElements2.values) {
                const uengineProps3 = extensionElements2.values.find((v) => v.$type === 'uengine:Properties');
                if (uengineProps3 && uengineProps3.json) {
                    try {
                        const props3 = JSON.parse(uengineProps3.json);
                        if (props3.futureStatus) futureStatus = props3.futureStatus;
                    } catch (e) {
                        /* ignore */
                    }
                }
            }

            if (futureStatus === 'sunset') {
                // Red dashed border + strikethrough name
                const sunsetBorder = svgCreate('rect');
                svgAttr(sunsetBorder, {
                    width: existingWidth,
                    height: existingHeight,
                    rx: TASK_BORDER_RADIUS,
                    ry: TASK_BORDER_RADIUS,
                    stroke: '#e53935',
                    strokeWidth: 2,
                    strokeDasharray: '6,3',
                    fill: 'none',
                    'pointer-events': 'none'
                });
                svgAppend(parentNode, sunsetBorder);
                // Strikethrough line over name
                const strikeY = existingHeight / 2;
                const strikeLine = svgCreate('line');
                svgAttr(strikeLine, {
                    x1: 10,
                    y1: strikeY,
                    x2: existingWidth - 10,
                    y2: strikeY,
                    stroke: '#e53935',
                    strokeWidth: 1.5,
                    'pointer-events': 'none'
                });
                svgAppend(parentNode, strikeLine);
            } else if (futureStatus === 'new') {
                // Blue glow border
                const glowBorder = svgCreate('rect');
                svgAttr(glowBorder, {
                    width: existingWidth + 4,
                    height: existingHeight + 4,
                    x: -2,
                    y: -2,
                    rx: TASK_BORDER_RADIUS + 2,
                    ry: TASK_BORDER_RADIUS + 2,
                    stroke: '#1565c0',
                    strokeWidth: 3,
                    strokeOpacity: 0.6,
                    fill: 'none',
                    'pointer-events': 'none'
                });
                svgAppend(parentNode, glowBorder);
            } else if (futureStatus === 'automation_planned') {
                // Orange dashed border + robot icon
                const autoBorder = svgCreate('rect');
                svgAttr(autoBorder, {
                    width: existingWidth,
                    height: existingHeight,
                    rx: TASK_BORDER_RADIUS,
                    ry: TASK_BORDER_RADIUS,
                    stroke: '#f57c00',
                    strokeWidth: 2,
                    strokeDasharray: '6,3',
                    fill: 'none',
                    'pointer-events': 'none'
                });
                svgAppend(parentNode, autoBorder);
                // Robot icon indicator
                const robotIcon = svgCreate('text');
                svgAttr(robotIcon, {
                    x: existingWidth - 14,
                    y: 14,
                    'font-size': '12px',
                    fill: '#f57c00',
                    'pointer-events': 'none'
                });
                robotIcon.textContent = '🤖';
                svgAppend(parentNode, robotIcon);
            }
            // 'maintain' = no visual change
        }

        // Display System Name / Menu Name below the Task
        if (systemName || menuName) {
            const labelParts = [];
            if (systemName) labelParts.push(systemName);
            if (menuName) labelParts.push(menuName);
            const labelText = labelParts.join(' / ');

            const metaLabel = svgCreate('text');
            svgAttr(metaLabel, {
                x: existingWidth / 2,
                y: existingHeight + 14,
                'text-anchor': 'middle',
                'font-size': '10px',
                'font-family': 'Arial, sans-serif',
                fill: '#666666',
                'font-style': 'italic'
            });
            metaLabel.textContent = `[${labelText}]`;
            svgAppend(parentNode, metaLabel);
        }
    }

    // StartEvnet 관련
    drawCustomStartEvent(parentNode, shape, element) {
        const size = 34;
        const radius = 100;
        var strokeColor = 'none';

        const borderRect = drawBorderRect(parentNode, size, size, radius, strokeColor);
        prependTo(borderRect, parentNode);
        const rect = drawRect(parentNode, size, size, radius, 'none', '#f6c745');
        prependTo(rect, parentNode);
        svgRemove(shape);
    }

    // endEvnet 관련
    drawCustomEndEvent(parentNode, shape, element) {
        const size = 34;
        const radius = 100;
        var strokeColor = 'none';

        const borderRect = drawBorderRect(parentNode, size, size, radius, strokeColor);
        prependTo(borderRect, parentNode);
        const rect = drawRect(parentNode, size, size, radius, 'none', '#f6c745');
        prependTo(rect, parentNode);
        svgRemove(shape);
    }

    // 이벤트끼리의 연결선과 화살표 관련
    drawConnection(parentNode, element) {
        if (is(element, 'bpmn:SequenceFlow')) {
            var strokeColor = 'black';

            const customMarkerUrl = createCustomMarker(parentNode, strokeColor);

            const currentWaypoints = element.waypoints;
            // waypoints가 없거나 부족하면 기본 렌더러 사용 (일부 엣지는 로드 순서 등으로 waypoints가 아직 없을 수 있음)
            if (!currentWaypoints || currentWaypoints.length < 2) {
                const options = {
                    stroke: strokeColor,
                    strokeWidth: '2',
                    markerEnd: customMarkerUrl
                };
                return this.bpmnRenderer.drawConnection(parentNode, element, options);
            }

            // Get all sequence flows to find intersections
            const allConnections = this.elementRegistry.filter((e) => is(e, 'bpmn:SequenceFlow'));

            // Find intersection points with other connections
            const intersections = [];
            allConnections.forEach((otherConn) => {
                if (otherConn.id === element.id) return;
                const otherWaypoints = otherConn.waypoints;
                if (!otherWaypoints || otherWaypoints.length < 2) return;

                // Check each segment of current connection against each segment of other connection
                for (let i = 0; i < currentWaypoints.length - 1; i++) {
                    for (let j = 0; j < otherWaypoints.length - 1; j++) {
                        const intersection = getLineIntersection(
                            currentWaypoints[i],
                            currentWaypoints[i + 1],
                            otherWaypoints[j],
                            otherWaypoints[j + 1]
                        );
                        if (intersection) {
                            intersections.push({
                                point: intersection,
                                segmentIndex: i
                            });
                        }
                    }
                }
            });

            // Sort intersections by distance from start of each segment
            intersections.sort((a, b) => {
                if (a.segmentIndex !== b.segmentIndex) {
                    return a.segmentIndex - b.segmentIndex;
                }
                const startA = currentWaypoints[a.segmentIndex];
                const startB = currentWaypoints[b.segmentIndex];
                const distA = Math.hypot(a.point.x - startA.x, a.point.y - startA.y);
                const distB = Math.hypot(b.point.x - startB.x, b.point.y - startB.y);
                return distA - distB;
            });

            try {
                // Draw path with line jumps at intersections
                if (intersections.length > 0) {
                    const path = createPathWithLineJumps(currentWaypoints, intersections);

                    svgAttr(path, {
                        stroke: strokeColor,
                        strokeWidth: '2',
                        fill: 'none',
                        markerEnd: customMarkerUrl
                    });

                    svgAppend(parentNode, path);
                    return path;
                }
            } catch (err) {
                console.warn('[CustomBpmnRenderer] drawConnection line-jump failed, using default:', element.id, err);
            }

            // No intersections or fallback: draw normal connection
            const options = {
                stroke: strokeColor,
                strokeWidth: '2',
                markerEnd: customMarkerUrl
            };

            var connection = this.bpmnRenderer.drawConnection(parentNode, element, options);
            return connection;
        }

        return this.bpmnRenderer.drawConnection(parentNode, element);
    }
    // bpmn:Gateway 관련
    drawCustomGateway(parentNode, shape, element) {
        const existingWidth = shape.getBoundingClientRect().width;
        const existingHeight = shape.getBoundingClientRect().height;

        const points = [
            { x: existingWidth / 2, y: 0 },
            { x: existingWidth, y: existingHeight / 2 },
            { x: existingWidth / 2, y: existingHeight },
            { x: 0, y: existingHeight / 2 }
        ]
            .map((point) => `${point.x},${point.y}`)
            .join(' ');

        const diamond = drawPolygon(parentNode, points);

        copyAttributes(shape, diamond);
        var strokeColor = '#000000';
        diamond.style.stroke = strokeColor;
        diamond.style.strokeWidth = strokeColor === '#000000' ? '2' : '5';
        if (strokeColor != '#000000') {
            diamond.style.strokeDasharray = '10, 10';
        }

        prependTo(diamond, parentNode);

        svgRemove(shape);
    }

    // bpmn:SubProcess 관련
    drawCustomSubProcess(parentNode, shape, element) {
        const existingWidth = shape.width.baseVal.value;
        const existingHeight = shape.height.baseVal.value;

        var strokeColor = '#000000';

        const borderRect = drawBorderRect(parentNode, existingWidth, existingHeight, TASK_BORDER_RADIUS, strokeColor);
        prependTo(borderRect, parentNode);
        const rect = drawRect(parentNode, existingWidth, existingHeight, TASK_BORDER_RADIUS, '#000000', '#ffffff');
        prependTo(rect, parentNode);
        svgRemove(shape);
    }

    getShapePath(shape) {
        if (is(shape, 'bpmn:Task')) {
            return getRoundRectPath(shape, TASK_BORDER_RADIUS);
        }

        return this.bpmnRenderer.getShapePath(shape);
    }
}

CustomBpmnRenderer.$inject = ['eventBus', 'bpmnRenderer', 'canvas', 'config', 'elementRegistry', 'graphicsFactory'];

// 연결선에 붙은 화살표 관련
function createCustomMarker(parentNode, color) {
    const marker = svgCreate('marker');
    const path = svgCreate('path');

    svgAttr(marker, {
        id: 'custom-arrow',
        viewBox: '0 0 10 10',
        refX: '9',
        refY: '5',
        markerWidth: '6',
        markerHeight: '6',
        orient: 'auto'
    });

    svgAttr(path, {
        d: 'M 0 0 L 10 5 L 0 10 z',
        fill: color
    });

    svgAppend(marker, path);
    svgAppend(parentNode, marker);

    return 'url(#custom-arrow)';
}
// 그림자 추가
function addShadowFilter(parentNode) {
    const defs = svgCreate('defs');
    const filter = svgCreate('filter');
    const feDropShadow = svgCreate('feDropShadow');

    svgAttr(filter, {
        id: 'dropshadow',
        height: '130%'
    });

    svgAttr(feDropShadow, {
        dx: '1', // X축 오프셋
        dy: '1', // Y축 오프셋
        stdDeviation: '3', // 블러 정도
        'flood-opacity': '0.3'
    });

    svgAppend(filter, feDropShadow);
    svgAppend(defs, filter);
    svgAppend(parentNode, defs);

    return 'url(#dropshadow)';
}

function drawRect(parentNode, width, height, borderRadius, strokeColor, fillColor) {
    const rect = svgCreate('rect');

    const filterId = addShadowFilter(parentNode);

    svgAttr(rect, {
        width: width,
        height: height,
        rx: borderRadius,
        ry: borderRadius,
        stroke: strokeColor,
        strokeWidth: 2,
        fill: fillColor || '#fff',
        filter: filterId
    });

    svgAppend(parentNode, rect);

    return rect;
}

/**
 * 노치 태그 그리기 (가로: 왼쪽 노치, 오른쪽 뾰족)
 * @param {boolean} vertical - true면 같은 모양을 시계 방향 90° 회전해서 그림
 */
function drawNotchTag(parentNode, width, height, fillColor, strokeColor, x = 0, y = 0, vertical = false) {
    const notchDepth = 30;
    const tipSize = 30;
    const notchSize = -notchDepth;

    const w = vertical ? height : width;
    const h = vertical ? width : height;

    const pathData = `
    M ${notchSize},0
    L ${w - tipSize},0
    L ${w},${h / 2}
    L ${w - tipSize},${h}
    L ${notchSize},${h}
    L 0,${h / 2}
    Z
  `;

    let transform;
    if (vertical) {
        const pathCenterX = w / 2 - notchDepth / 2;
        const pathCenterY = h / 2;
        const topOffset = notchDepth;
        transform = `translate(${x}, ${y + topOffset}) translate(${width / 2}, ${height / 2}) scale(-1, -1) translate(${-width / 2}, ${
            -height / 2
        }) translate(${h / 2}, ${w / 2 + notchDepth / 2}) rotate(-90) translate(${-pathCenterX}, ${-pathCenterY})`;
    } else {
        transform = `translate(${x + notchDepth}, ${y})`;
    }

    const path = svgCreate('path');
    svgAttr(path, {
        d: pathData,
        fill: fillColor,
        stroke: strokeColor,
        strokeWidth: 2,
        transform
    });

    svgAppend(parentNode, path);
    return path;
}

function drawBorderRect(parentNode, width, height, borderRadius, strokeColor, strokeWidth) {
    const borderRect = svgCreate('rect');

    svgAttr(borderRect, {
        width: width,
        height: height,
        rx: borderRadius,
        ry: borderRadius,
        stroke: strokeColor == '#000000' ? 'none' : strokeColor,
        strokeWidth: strokeWidth ? strokeWidth : 2,
        fill: 'none'
    });
    svgAppend(parentNode, borderRect);
    return borderRect;
}

function drawPolygon(parentNode, points) {
    const polygon = svgCreate('polygon');

    // 필터를 추가하고, 필터 ID를 가져옴
    const filterId = addShadowFilter(parentNode);

    svgAttr(polygon, {
        points: points,
        filter: filterId // 필터 적용
    });

    svgAppend(parentNode, polygon);

    return polygon;
}

function updateTextPosition(element, phaseVisual) {
    let textElement = phaseVisual.querySelector('text');
    if (!textElement) {
        textElement = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        textElement.setAttribute('text-anchor', 'middle');
        textElement.setAttribute('alignment-baseline', 'middle');
        textElement.style.fill = '#333'; // 텍스트 색상
        textElement.style.fontSize = '14px'; // 폰트 크기
        phaseVisual.appendChild(textElement);
    }

    // ✅ 텍스트 내용 설정
    textElement.textContent = element.businessObject.name || 'Phase';

    // ✅ 위치 조정
    const bbox = phaseVisual.getBBox();
    textElement.setAttribute('x', bbox.x + bbox.width / 2); // 중앙 정렬
    textElement.setAttribute('y', bbox.y + bbox.height / 2 + 5); // 중앙 + 약간 아래
}

function copyAttributes(source, target) {
    const attributes = source.attributes;
    for (let i = 0; i < attributes.length; i++) {
        const attr = attributes[i];
        target.setAttribute(attr.name, attr.value);
    }
}
// copied from https://github.com/bpmn-io/diagram-js/blob/master/lib/core/GraphicsFactory.js
function prependTo(newNode, parentNode, siblingNode) {
    parentNode.insertBefore(newNode, siblingNode || parentNode.firstChild);
}

// Line intersection detection
function getLineIntersection(p1, p2, p3, p4) {
    const x1 = p1.x,
        y1 = p1.y;
    const x2 = p2.x,
        y2 = p2.y;
    const x3 = p3.x,
        y3 = p3.y;
    const x4 = p4.x,
        y4 = p4.y;

    const denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4);
    if (Math.abs(denom) < 0.0001) return null; // Lines are parallel

    const t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom;
    const u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom;

    // Check if intersection is within both line segments (with small margin)
    const margin = 0.01;
    if (t > margin && t < 1 - margin && u > margin && u < 1 - margin) {
        return {
            x: x1 + t * (x2 - x1),
            y: y1 + t * (y2 - y1)
        };
    }
    return null;
}

// Create SVG path with line jumps (arcs) at intersection points
function createPathWithLineJumps(waypoints, intersections) {
    const JUMP_RADIUS = 6; // Radius of the arc jump
    const path = svgCreate('path');

    let d = '';
    let currentSegmentIndex = 0;
    let intersectionIdx = 0;

    for (let i = 0; i < waypoints.length - 1; i++) {
        const start = waypoints[i];
        const end = waypoints[i + 1];

        // Calculate segment direction
        const dx = end.x - start.x;
        const dy = end.y - start.y;
        const length = Math.hypot(dx, dy);
        const ux = dx / length; // Unit vector x
        const uy = dy / length; // Unit vector y

        if (i === 0) {
            d += `M ${start.x} ${start.y}`;
        }

        // Get intersections for this segment
        const segmentIntersections = [];
        while (intersectionIdx < intersections.length && intersections[intersectionIdx].segmentIndex === i) {
            segmentIntersections.push(intersections[intersectionIdx].point);
            intersectionIdx++;
        }

        // Sort by distance from segment start
        segmentIntersections.sort((a, b) => {
            const distA = Math.hypot(a.x - start.x, a.y - start.y);
            const distB = Math.hypot(b.x - start.x, b.y - start.y);
            return distA - distB;
        });

        if (segmentIntersections.length === 0) {
            // No intersections, draw straight line
            d += ` L ${end.x} ${end.y}`;
        } else {
            // Draw line with arcs at intersection points
            let lastPoint = start;

            for (const intersection of segmentIntersections) {
                // Point before the arc
                const beforeX = intersection.x - ux * JUMP_RADIUS;
                const beforeY = intersection.y - uy * JUMP_RADIUS;

                // Point after the arc
                const afterX = intersection.x + ux * JUMP_RADIUS;
                const afterY = intersection.y + uy * JUMP_RADIUS;

                // Draw line to before point
                d += ` L ${beforeX} ${beforeY}`;

                // Draw arc (semicircle) over the intersection
                // The arc goes perpendicular to the line direction
                // sweep-flag = 1 for clockwise arc (jump over)
                d += ` A ${JUMP_RADIUS} ${JUMP_RADIUS} 0 0 1 ${afterX} ${afterY}`;

                lastPoint = { x: afterX, y: afterY };
            }

            // Draw line from last arc to segment end
            d += ` L ${end.x} ${end.y}`;
        }
    }

    svgAttr(path, { d: d });
    return path;
}

// Explicit DI annotation so name-based injection survives a minified prod build.
CustomBpmnRenderer.$inject = [
    'eventBus', 'bpmnRenderer', 'canvas', 'config', 'elementRegistry', 'graphicsFactory'
];
