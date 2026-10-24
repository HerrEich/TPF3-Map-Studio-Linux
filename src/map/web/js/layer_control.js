console.log("LayerControl geladen");


class LayerControl {


    constructor(layerManager) {

        this.layerManager = layerManager;

        this.init();

    }



    init() {

        this.initCollapse();

        document
            .querySelectorAll('#layer-control input[type="checkbox"]')
            .forEach(input => {


                input.addEventListener(
                    "change",
                    () => {

                        this.layerManager.toggle(
                            input.dataset.layer
                        );

                    }
                );


            });



        document
            .getElementById("layers-on")
            .addEventListener(
                "click",
                () => {

                    document
                        .querySelectorAll('#layer-control input[type="checkbox"]')
                        .forEach(input => {

                            if (!input.checked) {

                                input.checked = true;

                                this.layerManager.toggle(
                                    input.dataset.layer
                                );

                            }

                        });

                }
            );


        document
            .getElementById("layers-off")
            .addEventListener(
                "click",
                () => {

                    document
                        .querySelectorAll('#layer-control input[type="checkbox"]')
                        .forEach(input => {

                            if (input.checked) {

                                input.checked = false;

                                this.layerManager.toggle(
                                    input.dataset.layer
                                );

                            }

                        });

                }
            );


    }


    // Klappt das ganze Fenster ein oder aus (Zustand wird gemerkt).
    initCollapse() {

        const panel = document.getElementById("layer-control");
        const button = document.getElementById("layer-collapse");

        if (!panel || !button) {
            return;
        }

        const apply = (collapsed) => {

            panel.classList.toggle("collapsed", collapsed);

            button.setAttribute("aria-expanded", String(!collapsed));

        };

        let collapsed = false;

        try {
            collapsed = localStorage.getItem("layerControlCollapsed") === "1";
        } catch (e) {
            collapsed = false;
        }

        apply(collapsed);

        button.addEventListener("click", () => {

            collapsed = !collapsed;

            apply(collapsed);

            try {
                localStorage.setItem("layerControlCollapsed", collapsed ? "1" : "0");
            } catch (e) {
                // Speichern ist nur eine Bequemlichkeit.
            }

        });

    }


}