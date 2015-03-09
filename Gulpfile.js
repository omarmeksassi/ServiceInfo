var gulp = require('gulp')
,   rename = require('gulp-rename')
,   less = require('gulp-less')
,   bg = require('gulp-bg')
,   browserify = require('gulp-browserify')
,   minimist = require('minimist')
,   child_process = require('child_process')
;

var knownOptions = {
    default: {
        config: "base",
    }
}

var options = minimist(process.argv.slice(2), knownOptions);

var API_PORT = 4005;
var EXPRESS_PORT = 8000;
var EXPRESS_ROOT = __dirname + "/frontend";
var LIVERELOAD_PORT = 3572;

function startExpress() {
    build();

    var express = require('express');
    var app = express();
    app.use(require('connect-livereload')());
    app.use(express.static(EXPRESS_ROOT));
    app.listen(EXPRESS_PORT);

    bg("python", "manage.py", "runserver", API_PORT)();
}

function startLiveReload() {
    lr = require('tiny-lr')();
    lr.listen(LIVERELOAD_PORT);
}

function injectEnvConfig() {
    gulp.src("frontend/config." + options.config + ".json")
        .pipe(rename("config.json"))
        .pipe(gulp.dest("frontend"))
    ;
}

function build() {
    gulp.src('frontend/styles/site-*.less')
        .pipe(less())
        .pipe(gulp.dest('frontend/styles'))
    ;

    var bundle = gulp.src('frontend/index.js')
        .pipe(browserify({
            insertGlobals : true,
            debug : options.config !== 'production',
            transform: ['hbsfy']
        }))
        .pipe(rename('bundle.js'))
        .pipe(gulp.dest('frontend'))
    ;

    child_process.execFile(
        'java',
        [
            '-jar', 'node_modules/closurecompiler/compiler/compiler.jar',
            '--language_in', 'ECMASCRIPT5',
            '--js_output_file', 'frontend/bundle_min.js',
            '--create_source_map', '%outname%.map',
            'frontend/bundle.js'
        ]
    );

    injectEnvConfig();
}

// Notifies livereload of changes detected
// by `gulp.watch()`
function notifyLivereload(event) {

    // `gulp.watch()` events provide an absolute path
    // so we need to make it relative to the server root
    var fileName = require('path').relative(EXPRESS_ROOT, event.path);

    build();

    setTimeout(function(){
        lr.changed({
            body: {
                files: [fileName]
            }
        });
    }, 500); // For some reason, triggering live reload too early serves the old version
}

gulp.task('default', function() {
    startExpress();
    startLiveReload();
    gulp.watch(['frontend/index.html', 'frontend/index.js', 'frontend/router.js', 'frontend/styles/site.less', 'frontend/templates/*.hbs', 'frontend/views/*.js'], notifyLivereload);
});

gulp.task('build', build);
