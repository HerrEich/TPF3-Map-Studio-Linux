console.log("ImportManager geladen");


class ImportManager {


    constructor(geometryManager) {

        this.geometry = geometryManager;

    }



    importFile(file) {


        const reader = new FileReader();



        reader.onload = (event) => {

            try {
                this.processImportData(
                    event.target.result
                );
            } catch (error) {
                console.error("JSON Import Fehler:", error);
                alert("JSON Import fehlgeschlagen: " + error.message);
            }

        };

        reader.onerror = () => {
            alert("Die Datei konnte nicht gelesen werden.");
        };

        reader.readAsText(file);

    }

    //====================================================
    // PROCESS IMPORT DATA
    //====================================================

    processImportData(text) {

        const data = JSON.parse(
            text
        );

        console.log(
           "IMPORT DATA:",
            data
        );

        this.loadObjects(
            data
        );

    }



    loadObjects(objects) {


        console.log(
            "IMPORT OBJECTS:",
            objects
        );

        if (!Array.isArray(objects)) {
            throw new Error("Die Datei enthaelt keine Objektliste.");
        }

        for (const name of ["roads", "railways", "buildings", "water",
                            "waterways", "parks", "landuse", "vegetation"]) {
            this.geometry.clear(name);
        }

        let ok = 0;
        let failed = 0;
        let firstError = null;


        for (const object of objects) {

            try {
                this.geometry.draw(object);
                ok++;
            } catch (error) {
                failed++;
                if (!firstError) {
                    firstError = error;
                }
            }

        }

        if (failed > 0) {
            alert("JSON Import: " + ok + " Objekte geladen, " + failed +
                  " fehlgeschlagen. Erster Fehler: " + firstError.message);
        } else {
            alert("JSON Import: " + ok + " Objekte geladen.");
        }


        console.log(
            "IMPORT FERTIG"
        );

    }
}
