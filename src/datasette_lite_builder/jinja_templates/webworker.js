importScripts("https://cdn.jsdelivr.net/pyodide/v0.24.0/full/pyodide.js");

function log(line) {
  console.log({line})
  self.postMessage({type: 'log', line: line});
}

async function startDatasette(settings) {
  let toLoad = [];
  let templateFiles = [];
  let sources = [];
  let needsDataDb = false;
  let shouldLoadDefaults = true;
  if (settings.initialUrl) {
    let name = settings.initialUrl.split('.db')[0].split('/').slice(-1)[0];
    toLoad.push([name, settings.initialUrl]);
    shouldLoadDefaults = false;
  }
  ['csv', 'sql', 'json', 'parquet'].forEach(sourceType => {
    if (settings[`${sourceType}Urls`] && settings[`${sourceType}Urls`].length) {
      sources.push([sourceType, settings[`${sourceType}Urls`]]);
      needsDataDb = true;
      shouldLoadDefaults = false;
    }
  });
  if (settings.memory) {
    shouldLoadDefaults = false;
  }
  if (needsDataDb) {
    toLoad.push(["data.db", 0]);
  }
  if (shouldLoadDefaults) {
    toLoad.push(["fixtures.db", "https://latest.datasette.io/fixtures.db"]);
    toLoad.push(["content.db", "https://datasette.io/content.db"]);
  }

  // 

  self.pyodide = await loadPyodide({
    indexURL: "https://cdn.jsdelivr.net/pyodide/v0.24.0/full/",
    packages: ["micropip", "setuptools", "ssl"],
    fullStdLib: true
  });
  self.pyodide.globals.set("_settings", settings);
  self.pyodide.globals.set("_to_load", toLoad);
  self.pyodide.globals.set("_sources", sources);
  try {
    await self.pyodide.runPythonAsync(`{{ web_worker_py }}`);
    await self.pyodide.runPythonAsync(`    
    
    settings = _settings.to_py()
    to_load = _to_load.to_py()
    sources = _sources.to_py()

    ds = await load_datasette(
          install_urls = settings["installUrls"],
          default_metadata = settings["default_metadata"],
          metadata_url = settings.get("metadataUrl", None),
          sources = sources,
          memory_setting = settings["memory"],
          data_to_load = to_load,
          config_static = settings["config_static"]
          )
            
    
    `);
    datasetteLiteReady();
  } catch (error) {
    self.postMessage({error: error.message});
  }
}

// Outside promise pattern
// https://github.com/simonw/datasette-lite/issues/25#issuecomment-1116948381
let datasetteLiteReady;
let readyPromise = new Promise(function(resolve) {
  datasetteLiteReady = resolve;
});

self.onmessage = async (event) => {
  console.log({event, data: event.data});
  if (event.data.type == 'startup') {
    await startDatasette(event.data);
    return;
  }
  // make sure loading is done
  await readyPromise;
  console.log(event, event.data);
  try {
    let [status, contentType, text] = await self.pyodide.runPythonAsync(
      `get_lite_response(ds, ${JSON.stringify(event.data.path)})`
    );
    path = event.data.path;
    self.postMessage({status, contentType, text, path});
  } catch (error) {
    self.postMessage({error: error.message});
  }
};
