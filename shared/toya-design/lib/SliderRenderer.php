<?php
declare(strict_types=1);
namespace Toya\Design;

final class SliderRenderer
{
    private static function e(mixed $s): string { return htmlspecialchars((string)$s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }
    private static function css(mixed $s, string $fallback): string
    {
        return is_scalar($s) && preg_match('/\A[\w\s#().,%+-]+\z/u', (string)$s) ? (string)$s : $fallback;
    }
    private static function url(mixed $s): string
    {
        $s = is_string($s) ? trim($s) : '';
        return preg_match('/[\x00-\x20\\\\]/', $s) || (preg_match('/^[a-z][a-z0-9+.-]*:/i', $s) && !preg_match('/^https?:/i', $s)) ? '' : $s;
    }
    public static function render(array $slide): string
    {
        if (empty($slide['is_active'])) { return ''; }
        $bg = self::url($slide['gorsel_url'] ?? '');
        $out = '<section class="toya-slider" aria-label="' . self::e($slide['baslik'] ?? 'Tanıtım') . '">';
        if ($bg !== '') { $out .= '<img class="toya-slider-bg" alt="" src="' . self::e($bg) . '">'; }
        $opacity = max(0, min(100, (float)($slide['overlay_opaklik'] ?? 40))) / 100;
        if (($slide['overlay_tipi'] ?? '') !== 'none') {
            $out .= '<div class="toya-slider-overlay" style="opacity:' . $opacity . '"></div>';
        }
        foreach (($slide['layers'] ?? []) as $layer) {
            if (!is_array($layer)) { continue; }
            $anim = in_array($layer['animation'] ?? '', ['fade-up','fade-down','slide-left','slide-right','zoom-in','rotate-in','bounce-in','parallax'], true) ? $layer['animation'] : 'fade-up';
            $style = 'left:' . (float)($layer['x'] ?? 0) . '%;top:' . (float)($layer['y'] ?? 0) . '%;';
            foreach (['width'=>'auto','height'=>'auto'] as $key=>$default) {
                $v = $layer[$key] ?? $default;
                $style .= $key . ':' . (is_numeric($v) ? $v . 'px' : self::css($v, $default)) . ';';
            }
            foreach (['fontSize'=>'font-size','borderRadius'=>'border-radius'] as $key=>$prop) { $style .= $prop . ':' . (float)($layer[$key] ?? ($key === 'fontSize' ? 16 : 0)) . 'px;'; }
            foreach (['fontWeight'=>['font-weight','400'],'color'=>['color','#fff'],'bgColor'=>['background-color','transparent'],'padding'=>['padding','0px'],'border'=>['border','none']] as $key=>$pair) { $style .= $pair[0] . ':' . self::css($layer[$key] ?? $pair[1], $pair[1]) . ';'; }
            $style .= 'z-index:' . (int)($layer['zIndex'] ?? 10) . ';--del:' . max(0, min(60, (float)($layer['delay'] ?? 0))) . 's;--dur:' . max(.01, min(60, (float)($layer['duration'] ?? .8))) . 's;';
            $content = (string)($layer['content'] ?? '');
            $out .= '<div class="toya-slider-layer play-anim-' . $anim . '" style="' . self::e($style) . '">';
            if (($layer['type'] ?? '') === 'image') {
                $out .= '<img alt="" src="' . self::e(self::url($content)) . '" style="max-width:100%;max-height:100%">';
            } elseif (($layer['type'] ?? '') === 'button') {
                $out .= '<a target="_top" href="' . self::e(self::url($layer['linkUrl'] ?? '#')) . '" style="color:inherit;text-decoration:none">' . self::e($content) . '</a>';
            } else {
                // Editor allows rich text. Public host additionally disables scripts with CSP.
                $out .= $content;
            }
            $out .= '</div>';
        }
        return $out . '</section>';
    }
}
