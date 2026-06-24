#!/usr/bin/env python3
"""OKF Serve — built-in visualizer for Open Knowledge Format bundles.

Start a local web server, open the bundle in your browser.
One command, zero config, no backend beyond Python's stdlib.

Usage:
    okf serve [path] [--port PORT]
"""

import argparse
import json
import os
import re
import sys
import urllib.parse
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / 'scripts'))

# ─── HTML template ──────────────────────────────────────────────────────────

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>OKF Visualizer — {{title}}</title>
<style>
:root{--bg:#0d1117;--surface:#161b22;--border:#30363d;--text:#c9d1d9;--dim:#8b949e;--bright:#f0f6fc;--accent:#58a6ff;--green:#3fb950;--amber:#d2991d;--red:#f85149;--purple:#bc8cff;--radius:6px;--font:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;--mono:'SF Mono','Fira Code',monospace}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);font-family:var(--font);font-size:15px;line-height:1.6;display:flex;min-height:100vh}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}

#sidebar{width:280px;min-width:280px;background:var(--surface);border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden}
#sidebar-header{padding:1rem;border-bottom:1px solid var(--border)}
#sidebar-header h1{font-size:1rem;color:var(--bright);font-weight:600}
#sidebar-header .sub{font-size:0.75rem;color:var(--dim);margin-top:0.25rem}
#sidebar-search{padding:0.75rem 1rem;border-bottom:1px solid var(--border)}
#sidebar-search input{width:100%;background:var(--bg);border:1px solid var(--border);border-radius:var(--radius);color:var(--text);padding:0.4rem 0.6rem;font-size:0.82rem;font-family:var(--font)}
#sidebar-search input::placeholder{color:var(--dim)}
#sidebar-tree{flex:1;overflow-y:auto;padding:0.5rem 0}
.tree-item{display:flex;align-items:center;padding:0.35rem 1rem;cursor:pointer;font-size:0.82rem;gap:0.4rem;color:var(--text);transition:background .1s}
.tree-item:hover{background:rgba(88,166,255,.08)}
.tree-item.active{background:rgba(88,166,255,.15);color:var(--accent)}
.tree-item .icon{font-size:0.65rem;width:20px;text-align:center;flex-shrink:0;background:var(--border);border-radius:3px;padding:0 2px;color:var(--dim);font-weight:500}
.tree-item .name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tree-item .badge{font-size:0.6rem;background:var(--border);border-radius:3px;padding:0 4px;color:var(--dim);margin-left:auto;flex-shrink:0}
.tree-dir{color:var(--bright);font-weight:500;font-size:0.75rem;padding:0.5rem 1rem 0.2rem;text-transform:uppercase;letter-spacing:.04em}
#sidebar-footer{padding:0.75rem 1rem;border-top:1px solid var(--border);font-size:0.7rem;color:var(--dim);display:flex;gap:1rem}
#sidebar-footer a{color:var(--dim)}#sidebar-footer a:hover{color:var(--accent)}

#main{flex:1;display:flex;flex-direction:column;overflow-y:auto}
#main-header{display:flex;align-items:center;gap:1rem;padding:1rem 1.5rem;border-bottom:1px solid var(--border)}
#main-header .breadcrumb{font-size:0.78rem;color:var(--dim)}
#main-header .breadcrumb span{color:var(--text)}
#main-body{padding:1.5rem 2rem 3rem;max-width:860px;flex:1}

.concept-header{margin-bottom:1.5rem}
.concept-header .type-badge{display:inline-block;font-size:0.72rem;padding:2px 8px;border-radius:12px;margin-bottom:0.5rem;background:rgba(88,166,255,.15);color:var(--accent);border:1px solid rgba(88,166,255,.3)}
.concept-header h2{font-size:1.5rem;color:var(--bright);font-weight:600;margin:0.25rem 0}
.concept-header .desc{font-size:0.9rem;color:var(--dim);margin:0.25rem 0}

.meta-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:0.5rem;margin:1rem 0;padding:0.75rem;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius)}
.meta-item{font-size:0.78rem}
.meta-item .key{color:var(--dim);font-weight:500}
.meta-item .val{color:var(--text)}
.meta-item .tags{display:flex;gap:0.25rem;flex-wrap:wrap;margin-top:0.15rem}
.meta-item .tag{font-size:0.65rem;background:rgba(210,153,29,.15);color:var(--amber);border:1px solid rgba(210,153,29,.3);border-radius:3px;padding:0 4px}

.concept-body{font-size:0.92rem;line-height:1.7}
.concept-body h1,.concept-body h2,.concept-body h3{color:var(--bright);font-weight:600;margin:1.5em 0 0.4em}
.concept-body h1{font-size:1.3rem;border-bottom:1px solid var(--border);padding-bottom:0.3em}
.concept-body h2{font-size:1.1rem}
.concept-body h3{font-size:0.95rem}
.concept-body p{margin:0.5em 0}
.concept-body code{background:rgba(240,246,252,.08);padding:1px 5px;border-radius:3px;font-size:0.88em;font-family:var(--mono)}
.concept-body pre{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:0.8rem;overflow-x:auto;margin:0.6em 0;font-size:0.82rem}
.concept-body pre code{background:none;padding:0;font-size:inherit}
.concept-body blockquote{border-left:3px solid var(--amber);margin:0.6em 0;padding:0.2em 0 0.2em 0.8rem;color:var(--dim)}
.concept-body ul,.concept-body ol{padding-left:1.5rem;margin:0.4em 0}
.concept-body li{margin:0.15em 0}
.concept-body img{max-width:100%;border-radius:var(--radius)}
.concept-body table{border-collapse:collapse;width:100%;margin:0.6em 0;font-size:0.85rem}
.concept-body th,.concept-body td{border:1px solid var(--border);padding:0.4rem 0.6rem;text-align:left}
.concept-body th{background:var(--surface);color:var(--bright)}
.concept-body hr{border:none;border-top:1px solid var(--border);margin:1.2em 0}

#graph-container{display:none;position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:100;flex-direction:column}
#graph-container.active{display:flex}
#graph-header{display:flex;justify-content:space-between;align-items:center;padding:1rem 1.5rem;border-bottom:1px solid var(--border)}
#graph-header h3{color:var(--bright);font-size:1rem}
#graph-close{background:var(--surface);border:1px solid var(--border);color:var(--text);padding:0.3rem 0.8rem;border-radius:var(--radius);cursor:pointer;font-size:0.8rem}
#graph-canvas{flex:1;position:relative;overflow:hidden}
#graph-canvas canvas{position:absolute;inset:0}

.empty-state{text-align:center;padding:4rem 2rem;color:var(--dim)}
.empty-state .icon{font-size:2.5rem;margin-bottom:0.5rem}
.empty-state p{font-size:0.9rem}
</style>
</head>
<body>

<div id="sidebar">
  <div id="sidebar-header">
    <h1>{{title}}</h1>
    <div class="sub">{{count}} concepts · {{dirs}} directories</div>
  </div>
  <div id="sidebar-search">
    <input type="text" placeholder="Search concepts..." oninput="filterTree(this.value)">
  </div>
  <div id="sidebar-tree"></div>
  <div id="sidebar-footer">
    <a href="#" onclick="viewGraph();return false">Graph</a>
    <a href="#" onclick="viewHome();return false">Home</a>
    <span>OKF v0.1</span>
  </div>
</div>

<div id="main">
  <div id="main-header">
    <div class="breadcrumb" id="breadcrumb">Home</div>
  </div>
  <div id="main-body"></div>
</div>

<div id="graph-container">
  <div id="graph-header">
    <h3>Concept Graph</h3>
    <button id="graph-close" onclick="closeGraph()">Close</button>
  </div>
  <div id="graph-canvas"><canvas id="gc"></canvas></div>
</div>

<script>
var concepts = {{concepts_json}};
var currentConcept = null;
var graphVisible = false;

// ── markdown render (minimal) ──
function md(s) {
  if (!s) return '';
  s = s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  // code blocks
  s = s.replace(/```(\w*)\n([\s\S]*?)```/g, function(_,lang,code){
    return '<pre><code>'+code.replace(/\n$/,'')+'</code></pre>';
  });
  // inline code
  s = s.replace(/`([^`]+)`/g,'<code>$1</code>');
  // images
  s = s.replace(/!\[([^\]]*)\]\(([^)]+)\)/g,'<img src="$2" alt="$1">');
  // links
  s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g,'<a href="$2">$1</a>');
  // headers
  s = s.replace(/^#### (.+)$/gm,'<h4>$1</h4>');
  s = s.replace(/^### (.+)$/gm,'<h3>$1</h3>');
  s = s.replace(/^## (.+)$/gm,'<h2>$1</h2>');
  s = s.replace(/^# (.+)$/gm,'<h1>$1</h1>');
  // bold/italic
  s = s.replace(/\*\*\*(.+?)\*\*\*/g,'<strong><em>$1</em></strong>');
  s = s.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>');
  s = s.replace(/\*(.+?)\*/g,'<em>$1</em>');
  // hr
  s = s.replace(/^---$/gm,'<hr>');
  // blockquote
  s = s.replace(/^&gt; (.+)$/gm,'<blockquote>$1</blockquote>');
  // lists
  s = s.replace(/^- (.+)$/gm,'<li>$1</li>');
  s = s.replace(/(<li>.*<\/li>\n?)+/g,'<ul>$&</ul>');
  // tables
  s = s.replace(/^\|(.+)\|$/gm, function(line){
    var cells = line.split('|').filter(function(c){return c.trim();});
    if (/^[-:\s|]+$/.test(line)) return '';
    var tag = line.match(/^\|\s*[-:]+\s*\|/) ? 'th' : 'td';
    return '<tr>'+cells.map(function(c){return '<'+tag+'>'+c.trim()+'</'+tag+'>';}).join('')+'</tr>';
  });
  s = s.replace(/(<tr>.*<\/tr>\n?)+/g,'<table>$&</table>');
  // paragraphs
  s = s.replace(/\n\n+/g,'</p><p>');
  s = '<p>'+s+'</p>';
  s = s.replace(/<p>\s*<\/p>/g,'');
  return s;
}

// ── tree ──
function buildTree() {
  var root = {name:'/',children:{},concepts:[]};
  concepts.forEach(function(c){
    var parts = c.path.split('/');
    var node = root;
    for (var i=0;i<parts.length-1;i++){
      if (!parts[i]) continue;
      if (!node.children[parts[i]]) node.children[parts[i]] = {name:parts[i],children:{},concepts:[]};
      node = node.children[parts[i]];
    }
    node.concepts.push(c);
  });
  return root;
}

function renderTree(filter){
  var root = buildTree();
  var html = '';
  function walk(node,indent){
    var keys = Object.keys(node.children).sort();
    keys.forEach(function(k){
      html += '<div class="tree-dir">'+k+'/</div>';
      walk(node.children[k],indent+'  ');
    });
    node.concepts.forEach(function(c){
      if (filter && c.title.toLowerCase().indexOf(filter.toLowerCase()) === -1
          && c.type.toLowerCase().indexOf(filter.toLowerCase()) === -1
          && c.path.toLowerCase().indexOf(filter.toLowerCase()) === -1) return;
      var active = currentConcept && currentConcept.path === c.path ? ' active' : '';
      html += '<div class="tree-item'+active+'" onclick="viewConcept(\''+c.path.replace(/'/g,"\\'")+'\')">'
        +'<span class="icon">'+iconFor(c.type)+'</span>'
        +'<span class="name">'+esc(c.title||c.path)+'</span>'
        +'<span class="badge">'+c.type+'</span>'
        +'</div>';
    });
  }
  walk(root,'');
  document.getElementById('sidebar-tree').innerHTML = html || '<div class="tree-item" style="color:var(--dim)">No matches</div>';
}

function iconFor(type){
  var t = (type||'').toLowerCase();
  if (t.indexOf('runbook')>=0) return 'RB';
  if (t.indexOf('metric')>=0) return 'MT';
  if (t.indexOf('database')>=0||t.indexOf('table')>=0) return 'DB';
  if (t.indexOf('api')>=0) return 'AP';
  if (t.indexOf('social')>=0) return 'SM';
  if (t.indexOf('report')>=0||t.indexOf('daily')>=0) return 'RP';
  if (t.indexOf('note')>=0) return 'NT';
  if (t.indexOf('document')>=0) return 'DC';
  if (t.indexOf('knowledge')>=0) return 'KB';
  return '--';
}

function filterTree(q){ renderTree(q); }

// ── concept view ──
function viewConcept(path){
  var c = null;
  for (var i=0;i<concepts.length;i++){
    if (concepts[i].path === path){ c = concepts[i]; break; }
  }
  if (!c) return;
  currentConcept = c;
  renderTree();
  document.getElementById('breadcrumb').innerHTML = c.path.split('/').map(function(p,i,arr){
    return i===arr.length-1 ? '<span>'+p+'</span>' : p+'/';
  }).join('');

  var meta = c.meta || {};
  var tagsHtml = (c.tags||[]).map(function(t){return '<span class="tag">'+t+'</span>';}).join('');
  var metaHtml = '<div class="meta-grid">'
    + '<div class="meta-item"><span class="key">Type</span><br><span class="val">'+esc(c.type||'?')+'</span></div>';
  if (meta.resource) metaHtml += '<div class="meta-item"><span class="key">Resource</span><br><a href="'+esc(meta.resource)+'">'+esc(meta.resource).substring(0,40)+(meta.resource.length>40?'...':'')+'</a></div>';
  if (meta.timestamp) metaHtml += '<div class="meta-item"><span class="key">Updated</span><br><span class="val">'+esc(meta.timestamp).substring(0,10)+'</span></div>';
  if (c.tags && c.tags.length) metaHtml += '<div class="meta-item"><span class="key">Tags</span><br><div class="tags">'+tagsHtml+'</div></div>';
  metaHtml += '</div>';

  var bodyHtml = c.body ? '<div class="concept-body">'+md(c.body)+'</div>'
    : '<div class="empty-state"><p>No content body</p></div>';

  // Find links to other concepts
  var linkedConcepts = [];
  if (c.body){
    var re = /\[([^\]]+)\]\(([^)]+\.md)\)/g;
    var m;
    while ((m = re.exec(c.body)) !== null){
      var target = m[2];
      // resolve relative path
      var resolved = resolvePath(c.path, target);
      for (var i=0;i<concepts.length;i++){
        if (concepts[i].path === resolved){
          linkedConcepts.push(concepts[i]);
          break;
        }
      }
    }
  }

  var linkedHtml = '';
  if (linkedConcepts.length){
    linkedHtml = '<div style="margin-top:2rem"><h3 style="color:var(--bright);font-size:0.9rem">Linked Concepts</h3><div style="display:flex;flex-wrap:wrap;gap:0.5rem;margin-top:0.5rem">';
    linkedConcepts.forEach(function(lc){
      linkedHtml += '<div style="background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:0.5rem 0.75rem;cursor:pointer;font-size:0.82rem" onclick="viewConcept(\''+lc.path.replace(/'/g,"\\'")+'\')">'
        +esc(lc.title||lc.path)
        +'<div style="font-size:0.65rem;color:var(--dim)">'+esc(lc.type)+'</div></div>';
    });
    linkedHtml += '</div></div>';
  }

  document.getElementById('main-body').innerHTML =
    '<div class="concept-header">'
    +'<span class="type-badge">'+esc(c.type||'Unknown')+'</span>'
    +'<h2>'+esc(c.title||c.path)+'</h2>'
    +(meta.description ? '<div class="desc">'+esc(meta.description)+'</div>' : '')
    +'</div>'
    +metaHtml
    +bodyHtml
    +linkedHtml;
}

function resolvePath(from, target){
  var parts = from.split('/');
  parts.pop(); // remove filename
  var tparts = target.split('/');
  for (var i=0;i<tparts.length;i++){
    if (tparts[i]==='..') parts.pop();
    else if (tparts[i]!=='.') parts.push(tparts[i]);
  }
  return parts.join('/');
}

function viewHome(){
  currentConcept = null;
  renderTree();
  document.getElementById('breadcrumb').innerHTML = 'Home';
  var types = {};
  var totalConcepts = concepts.length;
  var totalDirs = {{dirs}};
  concepts.forEach(function(c){ types[c.type] = (types[c.type]||0)+1; });

  var intro = '<div style="margin-bottom:2rem;padding:1.5rem;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius)">'
    +'<h2 style="color:var(--bright);font-size:1.3rem;margin-bottom:0.5rem">{{title}}</h2>'
    +'<p style="color:var(--dim);font-size:0.9rem;line-height:1.6">Open Knowledge Format (OKF) 知识库。左侧树形目录按文件组织，点击任意概念查看详情，输入框搜索，底部 <strong>Graph</strong> 查看概念关系图。所有内容以 markdown + YAML frontmatter 存储，人和 AI 都能直接阅读。</p>'
    +'<div style="display:flex;gap:1.5rem;margin-top:1rem;font-size:0.82rem">'
    +'<div style="color:var(--accent)"><strong>'+totalConcepts+'</strong> 个概念</div>'
    +'<div style="color:var(--green)"><strong>'+Object.keys(types).length+'</strong> 种类型</div>'
    +'<div style="color:var(--amber)"><strong>'+totalDirs+'</strong> 个目录</div>'
    +'</div></div>';

  var typeCards = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:0.75rem">'
    +Object.keys(types).sort().map(function(t){
      return '<div style="background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:1rem;cursor:pointer" onclick="filterByType(\''+t.replace(/'/g,"\\'")+'\')">'
      +'<div style="font-weight:600;color:var(--bright);font-size:0.88rem">'+esc(t)+'</div>'
      +'<div style="font-size:0.75rem;color:var(--dim);margin-top:0.2rem">'+types[t]+' concepts</div>'
      +'</div>';
    }).join('')+'</div>';

  document.getElementById('main-body').innerHTML = intro + typeCards;
}

function filterByType(type){
  currentConcept = null;
  var filtered = concepts.filter(function(c){return c.type===type;});
  // show all matching in main
  var items = filtered.map(function(c){
    return '<div style="background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:0.75rem 1rem;cursor:pointer" onclick="viewConcept(\''+c.path.replace(/'/g,"\\'")+'\')">'
      +'<div style="font-weight:500;color:var(--bright);font-size:0.9rem">'+esc(c.title||c.path)+'</div>'
      +'<div style="font-size:0.72rem;color:var(--dim)">'+c.path+'</div>'
      +'</div>';
  }).join('');
  document.getElementById('breadcrumb').innerHTML = '<span>'+type+'</span>';
  document.getElementById('main-body').innerHTML =
    '<h2 style="color:var(--bright);font-size:1.1rem;margin-bottom:1rem">'+type+' ('+filtered.length+' concepts)</h2>'
    +'<div style="display:flex;flex-direction:column;gap:0.4rem">'+items+'</div>';
}

// ── graph ──
function viewGraph(){
  document.getElementById('graph-container').classList.add('active');
  var container = document.getElementById('graph-canvas');
  var canvas = document.getElementById('gc');
  canvas.width = container.clientWidth;
  canvas.height = container.clientHeight;
  var ctx = canvas.getContext('2d');

  // Build graph: nodes = concepts, edges = links
  var nodes = concepts.map(function(c,i){
    return {id:i, label:c.title||c.path, path:c.path, type:c.type, x:0, y:0, vx:0, vy:0};
  });
  var nodeMap = {};
  nodes.forEach(function(n){ nodeMap[n.path] = n; });

  var edges = [];
  concepts.forEach(function(c){
    if (!c.body) return;
    var re = /\[([^\]]+)\]\(([^)]+\.md)\)/g;
    var m;
    while ((m = re.exec(c.body)) !== null){
      var target = resolvePath(c.path, m[2]);
      if (nodeMap[target]){
        edges.push({from: nodeMap[c.path].id, to: nodeMap[target].id});
      }
    }
  });

  // Simple force layout
  var w = canvas.width, h = canvas.height;
  var cx = w/2, cy = h/2;
  nodes.forEach(function(n,i){
    var angle = (i/nodes.length)*Math.PI*2;
    n.x = cx + Math.cos(angle)*Math.min(w,h)*0.35;
    n.y = cy + Math.sin(angle)*Math.min(w,h)*0.35;
  });

  function sim(){
    var changed = false;
    // repulsion
    for (var i=0;i<nodes.length;i++){
      for (var j=i+1;j<nodes.length;j++){
        var dx = nodes[j].x - nodes[i].x;
        var dy = nodes[j].y - nodes[i].y;
        var d = Math.sqrt(dx*dx+dy*dy) || 0.1;
        var f = 500/(d*d);
        var fx = dx/d*f, fy = dy/d*f;
        nodes[i].vx -= fx; nodes[i].vy -= fy;
        nodes[j].vx += fx; nodes[j].vy += fy;
      }
    }
    // attraction (edges)
    edges.forEach(function(e){
      var dx = nodes[e.to].x - nodes[e.from].x;
      var dy = nodes[e.to].y - nodes[e.from].y;
      var d = Math.sqrt(dx*dx+dy*dy) || 0.1;
      var f = 0.01*d;
      nodes[e.from].vx += dx/d*f;
      nodes[e.from].vy += dy/d*f;
      nodes[e.to].vx -= dx/d*f;
      nodes[e.to].vy -= dy/d*f;
    });
    // center gravity
    nodes.forEach(function(n){
      n.vx += (cx-n.x)*0.001;
      n.vy += (cy-n.y)*0.001;
    });
    // update
    nodes.forEach(function(n){
      n.vx *= 0.85; n.vy *= 0.85;
      n.x += n.vx; n.y += n.vy;
      n.x = Math.max(20,Math.min(w-20,n.x));
      n.y = Math.max(20,Math.min(h-20,n.y));
      if (Math.abs(n.vx)>0.1||Math.abs(n.vy)>0.1) changed=true;
    });
    return changed;
  }

  function draw(){
    ctx.clearRect(0,0,w,h);
    // edges
    edges.forEach(function(e){
      ctx.beginPath();
      ctx.moveTo(nodes[e.from].x,nodes[e.from].y);
      ctx.lineTo(nodes[e.to].x,nodes[e.to].y);
      ctx.strokeStyle = 'rgba(48,54,61,0.6)';
      ctx.lineWidth = 1;
      ctx.stroke();
    });
    // nodes
    nodes.forEach(function(n){
      var r = 4 + (edges.filter(function(e){return e.from===n.id||e.to===n.id;}).length)*1.5;
      ctx.beginPath();
      ctx.arc(n.x,n.y,Math.min(r,12),0,Math.PI*2);
      ctx.fillStyle = '#58a6ff';
      ctx.fill();
      ctx.fillStyle = '#c9d1d9';
      ctx.font = '10px system-ui';
      ctx.fillText(n.label.substring(0,20), n.x+8, n.y+4);
    });
  }

  var iter = 0;
  function step(){
    if (iter < 100 && sim()){ iter++; requestAnimationFrame(step); draw(); }
    else draw();
  }
  step();

  // click on canvas
  var clickedNode = null;
  canvas.onclick = function(e){
    var rect = canvas.getBoundingClientRect();
    var mx = e.clientX-rect.left, my = e.clientY-rect.top;
    for (var i=0;i<nodes.length;i++){
      var dx = mx-nodes[i].x, dy = my-nodes[i].y;
      if (Math.sqrt(dx*dx+dy*dy) < 15){
        closeGraph();
        viewConcept(nodes[i].path);
        return;
      }
    }
  };
}

function closeGraph(){
  document.getElementById('graph-container').classList.remove('active');
}

function esc(s){ return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

// ── keyboard ──
document.addEventListener('keydown',function(e){
  if (e.key==='Escape') closeGraph();
});

// ── init ──
renderTree();
viewHome();
</script>
</body>
</html>"""


# ─── server ──────────────────────────────────────────────────────────────────

def load_bundle(root: str) -> dict:
    """Load all concepts from an OKF bundle directory."""
    concepts = []
    dirs = set()

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith('.')]
        for f in filenames:
            if not f.endswith('.md'):
                continue
            if f == 'index.md' or f == 'log.md':
                continue
            full = os.path.join(dirpath, f)
            relpath = os.path.relpath(full, root)
            dirs.add(os.path.dirname(relpath) or '.')

            try:
                with open(full) as fh:
                    raw = fh.read()
            except Exception:
                continue

            fm, body = _read_frontmatter_safe(raw)
            concepts.append({
                'path': relpath.replace('\\', '/'),
                'type': fm.get('type', 'Unknown') if fm else 'Unknown',
                'title': fm.get('title', f.replace('.md', '')) if fm else f,
                'description': fm.get('description', '') if fm else '',
                'tags': fm.get('tags', []) if fm else [],
                'meta': {
                    'resource': fm.get('resource', '') if fm else '',
                    'timestamp': _safe_str(fm.get('timestamp', '')) if fm else '',
                    'description': fm.get('description', '') if fm else '',
                } if fm else {},
                'body': body or '',
                'has_frontmatter': fm is not None,
            })

    return {
        'concepts': sorted(concepts, key=lambda c: c['path']),
        'dirs': len(dirs),
    }


def _read_frontmatter_safe(raw: str) -> tuple[dict | None, str | None]:
    """Parse frontmatter without PyYAML dependency issues."""
    if not raw.startswith('---'):
        return None, raw
    parts = raw.split('---', 2)
    if len(parts) < 3:
        return None, raw
    try:
        import yaml
        fm = yaml.safe_load(parts[1])
        if isinstance(fm, dict):
            return fm, parts[2]
    except Exception:
        pass

    # Fallback: simple key:value parser
    fm = {}
    for line in parts[1].strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('- '):
            continue
        m = re.match(r'^([\w_-]+)\s*:\s*["\']?(.*?)["\']?\s*$', line)
        if m:
            fm[m.group(1)] = m.group(2)
    return fm if fm else None, parts[2] if len(parts) > 2 else ''


def _safe_str(v) -> str:
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v) if v else ''


class OKFHandler(BaseHTTPRequestHandler):
    bundle_root = ''
    page_html = ''
    concepts_json = ''

    def log_message(self, format, *args):
        pass  # silent

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == '/' or path == '/index.html':
            self._serve_html()
        elif path == '/api/concepts':
            self._serve_json(self.concepts_json)
        else:
            self._serve_html()

    def _serve_html(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(self.page_html.encode('utf-8'))

    def _serve_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(data.encode('utf-8'))


def cmd_serve(args):
    """Start a local web server to browse the OKF bundle."""
    root = os.path.abspath(args.path or '.')
    port = args.port or 3000
    title = args.title or os.path.basename(root) or 'OKF Bundle'

    # Load concepts
    bundle = load_bundle(root)
    concepts = bundle['concepts']

    # Build page
    page = HTML_PAGE.replace('{{title}}', title)
    page = page.replace('{{count}}', str(len(concepts)))
    page = page.replace('{{dirs}}', str(bundle['dirs']))
    page = page.replace('{{concepts_json}}', json.dumps(concepts, ensure_ascii=False))

    # Patch handler
    OKFHandler.bundle_root = root
    OKFHandler.page_html = page
    OKFHandler.concepts_json = json.dumps(concepts, ensure_ascii=False)

    server = HTTPServer(('0.0.0.0', port), OKFHandler)

    print(f'\n  OKF Visualizer')
    print(f'  Bundle: {root}')
    print(f'  Concepts: {len(concepts)}')
    print(f'  URL: http://localhost:{port}')
    print(f'\n  Press Ctrl+C to stop\n')

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n  Shutting down...')
        server.shutdown()


# ─── register command ────────────────────────────────────────────────────────

def register_serve(subparsers):
    p = subparsers.add_parser('serve', help='Start local visualizer for an OKF bundle')
    p.add_argument('path', nargs='?', default='.', help='Bundle directory')
    p.add_argument('--port', '-p', type=int, default=3000, help='Port to listen on')
    p.add_argument('--title', help='Bundle title (default: directory name)')
    return p
