/* Theme-backed free positioning. Saved as ordinary GrapesJS components + CSS. */
(function () {
    'use strict';
    window.toyaFreeLayoutPlugin = function (editor) {
        const stageType = 'toya-free-stage';
        const layerType = 'toya-free-layer';
        const mobileCss = `
            @media (max-width: 767px) {
                .toya-free-stage { height: auto !important; min-height: 0 !important; display: flex !important; flex-direction: column; gap: 1.25rem; padding: 1.5rem; }
                .toya-free-stage > .toya-free-layer { position: relative !important; left: auto !important; top: auto !important; right: auto !important; bottom: auto !important; transform: none !important; width: 100% !important; max-width: 100% !important; height: auto !important; margin: 0 !important; }
            }
            .toya-free-layer img { max-width: 100%; height: auto; }
        `;
        editor.DomComponents.addType(layerType, {
            isComponent: el => el?.getAttribute?.('data-toya-free-layer') === '1',
            model: {
                defaults: {
                    name: 'Serbest Nesne',
                    attributes: {'data-toya-free-layer': '1'},
                    classes: ['toya-free-layer'],
                    draggable: '[data-toya-free-stage="1"]',
                    resizable: true,
                    style: {position: 'absolute', left: '40px', top: '40px', width: '280px'},
                    components: [{type: 'text', content: 'Metni düzenlemek için çift tıklayın.'}]
                },
                init() { this.setDragMode('absolute'); }
            }
        });
        editor.DomComponents.addType(stageType, {
            isComponent: el => el?.getAttribute?.('data-toya-free-stage') === '1',
            model: {
                defaults: {
                    name: 'Serbest Tasarım Alanı', tagName: 'section',
                    attributes: {'data-toya-free-stage': '1'}, classes: ['toya-free-stage'],
                    style: {position: 'relative', height: '520px', width: '100%', overflow: 'hidden'},
                    styles: mobileCss,
                    droppable: '[data-toya-free-layer="1"]',
                    resizable: {tl: false, tc: false, tr: false, cl: false, cr: false, bl: false, br: false, bc: true},
                    components: [
                        {type: layerType, style: {position: 'absolute', left: '8%', top: '20%', width: '55%'}, components: '<h2>Temanızla özgürce tasarlayın</h2>'},
                        {type: layerType, style: {position: 'absolute', left: '8%', top: '48%', width: '50%'}, components: '<p>Nesne çerçevesini seçip taşıyın. Renkler, yazılar ve butonlar tema stillerini kullanır.</p>'},
                        {type: layerType, style: {position: 'absolute', left: '8%', top: '72%', width: '220px'}, components: '<a class="btn btn-primary" href="#iletisim">İletişime geçin</a>'}
                    ]
                }
            }
        });
        const category = 'Serbest Tasarım';
        editor.BlockManager.add(stageType, {label: '▣ Serbest Tasarım Alanı', category, content: {type: stageType}});
        const blocks = [
            ['text', 'Metin', '<h3>Başlığınız</h3><p>Açıklamanız</p>'],
            ['button', 'Buton', '<a class="btn btn-primary" href="#iletisim">Bilgi alın</a>'],
            ['image', 'Görsel', {type: 'image'}],
            ['shape', 'Şekil / Kart', '<div class="bg-primary rounded-4" style="min-height:120px"></div>']
        ];
        blocks.forEach(([id, label, components]) => editor.BlockManager.add('toya-free-' + id, {
            label, category, content: {type: layerType, components}
        }));
        editor.StyleManager.addSector('toya-position', {
            name: 'Nesne Konumu ve Katman', open: false,
            properties: [
                {property: 'left', name: 'Soldan', type: 'integer', units: ['px', '%', 'rem'], defaults: '0px'},
                {property: 'top', name: 'Üstten', type: 'integer', units: ['px', '%', 'rem'], defaults: '0px'},
                {property: 'z-index', name: 'Katman sırası', type: 'integer'},
                {property: 'width', name: 'Genişlik', type: 'integer', units: ['px', '%', 'rem'], defaults: 'auto'},
                {property: 'height', name: 'Yükseklik', type: 'integer', units: ['px', '%', 'rem'], defaults: 'auto'}
            ]
        });
        const getLayer = component => {
            let current = component;
            while (current && current.get('type') !== layerType) current = current.parent();
            return current;
        };
        editor.Commands.add('toya-select-layer', {run() {
            const layer = getLayer(editor.getSelected());
            if (layer) editor.select(layer);
        }});
        editor.Commands.add('toya-layer-front', {run() {
            const layer = getLayer(editor.getSelected());
            if (!layer) return;
            const siblings = layer.parent().components().models;
            const highest = Math.max(0, ...siblings.map(item => parseInt(item.getStyle()['z-index'], 10) || 0));
            layer.addStyle({'z-index': highest + 1});
        }});
        editor.Commands.add('toya-layer-back', {run() {
            const layer = getLayer(editor.getSelected());
            if (!layer) return;
            const siblings = layer.parent().components().models;
            // Keep all layers above the stage background.
            siblings.filter(item => item !== layer).forEach(item => item.addStyle({'z-index': (parseInt(item.getStyle()['z-index'], 10) || 0) + 1}));
            layer.addStyle({'z-index': 0});
        }});
        editor.on('component:selected', component => {
            if (!getLayer(component)) return;
            const toolbar = component.get('toolbar') || [];
            const extra = [
                ['toya-select-layer', 'Nesne çerçevesini seç', 'fa fa-arrows-alt'],
                ['toya-layer-front', 'Öne getir', 'fa fa-arrow-up'],
                ['toya-layer-back', 'Arkaya gönder', 'fa fa-arrow-down']
            ];
            component.set('toolbar', toolbar.concat(extra.filter(([command]) => !toolbar.some(item => item.command === command))
                .map(([command, title, icon]) => ({command, attributes: {title, class: icon}}))));
        });
    };
})();
