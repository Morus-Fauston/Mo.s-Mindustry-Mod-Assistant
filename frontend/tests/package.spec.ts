import { test, expect } from '@playwright/test';
import { execFile, spawn, type ChildProcess } from 'node:child_process';
import { createHash } from 'node:crypto';
import { cp, mkdir, mkdtemp, readFile, writeFile, rename, rmdir, stat } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, parse, resolve } from 'node:path';
import { promisify } from 'node:util';
import { inflateRawSync } from 'node:zlib';

const executeFile = promisify(execFile);
interface Identity { pid: number; createdTicks: string; name: string }
interface NativeResult { target?: { value: string | null }; [key: string]: unknown }

// Production deliberately refuses CDP. Only Windows UIA and native dialogs are used.
test.describe.configure({ timeout: 300_000, retries: 0 });
test('正式目录包原生核心链：新建源码贴图保存故障导出关闭重开与重启', async ({}, info) => {
  const started = Date.now(), workDeadline = started + 260_000, cleanupDeadline = started + 290_000;
  const root = resolve(import.meta.dirname, '../..');
  const source = resolve(process.env.MOMA_TEST_PACKAGE_ROOT || join(root, 'dist/MoMA-Web'));
  const temporary = await mkdtemp(join(tmpdir(), 'moma-package-'));
  const packaged = join(temporary, '中文 发布包'), profile = join(temporary, '独立 用户');
  const project = join(temporary, '中文 空格工程'), exported = join(temporary, '中文 导出.zip');
  const createdProject = join(temporary, 'package-created'), png = join(temporary, '原生 中文贴图.png');
  const sprite = join(project, 'sprites/units/package-unit.png');
  const report: any = { pass: false, source, packaged, temporary, project, startedUtc: new Date(started).toISOString(),
    environment: '当前开发机，System32-only PATH，隔离用户目录；不是清洁 Windows 或离线机器验收',
    coverage: ['正式 EXE 无调试启动', '中文空格包与工程路径', '真实UI新建独立工程', '真实原生打开磁盘双内容fixture', '双内容数值编辑', '源码未知结构编辑', 'PNG原生导入撤销重做', '保存拒绝恢复', '关于真实版本', '保存磁盘读回', '导出 ZIP 逐成员读回', '同宿主关闭工程重开', '正常关闭重启'],
    notCovered: ['键盘输入与快捷键体验', '新建内容类别与模板的UIA选择', 'PNG替换确认分支', '清洁 Windows', '离线首次启动', '完整 UI 与 DPI 矩阵'],
    lifecycleCoverage: '仅本次 launcher 及多次采样捕获的后代身份，不声称捕获采样间出生并重归属的全部短命后代',
    steps: [], launches: [], samples: [], forcedTermination: false, cleanupErrors: [] };
  let child: ChildProcess | undefined, spawnError: Error | undefined;
  let output = '', requestIndex = 0;
  const known = new Map<string, Identity>();
  const remaining = (maximum: number, cleanup = false, emergency = false) => {
    // Reserve the final ten cleanup seconds for identity-checked forced exit.
    const left = (cleanup ? cleanupDeadline - (emergency ? 0 : 10_000) : workDeadline) - Date.now();
    if (left <= 0) throw new Error('发布包验收共享时间预算耗尽');
    return Math.max(1, Math.min(maximum, left));
  };
  async function owned(action: 'sample' | 'check' | 'terminate', initialPid?: number, cleanup = false, emergency = false) {
    const args = ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File',
      resolve(import.meta.dirname, 'owned-processes.ps1'), '-Action', action, '-KnownJson', JSON.stringify([...known.values()])];
    if (initialPid) args.push('-RootProcessId', String(initialPid));
    const result = await executeFile('powershell.exe', args, { windowsHide: true, timeout: remaining(emergency ? 4_000 : 8_000, cleanup, emergency), maxBuffer: 1024 * 1024 });
    const data = JSON.parse(result.stdout);
    for (const value of data.identities ?? []) known.set(`${value.pid}:${value.createdTicks}`, value);
    report.samples.push(data);
    if (data.reused?.length && !emergency) throw new Error('本次已记录 PID 发生复用；拒绝操作复用进程');
    if (data.reused?.length && emergency) report.cleanupErrors.push('清理时发现 PID 复用，已保留复用进程，仅处理原创建时间匹配的身份');
    return data as { survivors?: Identity[] };
  }
  async function native(action: string, name = '', type = '', value = '', cleanup = false): Promise<NativeResult> {
    if (!cleanup && spawnError) throw spawnError;
    await owned('sample', undefined, cleanup);
    const request = join(temporary, `native-${++requestIndex}.json`);
    await writeFile(request, JSON.stringify({ action, name, type, value, identities: [...known.values()], timeoutMs: remaining(12_000, cleanup) }));
    let result;
    try {
      result = await executeFile('powershell.exe', ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
        '-File', resolve(import.meta.dirname, 'package-native.ps1'), '-RequestPath', request],
      { windowsHide: true, encoding: 'utf8', timeout: remaining(17_000, cleanup), maxBuffer: 8 * 1024 * 1024 });
    } catch (error) {
      const details = error as { stdout?: string; stderr?: string };
      await writeFile(info.outputPath(`native-${requestIndex}-${action}-failure.txt`), `${details.stdout ?? ''}\n${details.stderr ?? ''}\n${String(error)}`);
      throw error;
    }
    await writeFile(info.outputPath(`native-${requestIndex}-${action}.txt`), result.stdout);
    return ['dialog', 'close'].includes(action) ? {} : JSON.parse(result.stdout);
  }
  async function step(name: string, run: () => Promise<void>) {
    const entry = { name, passed: false, startedMs: Date.now() - started, elapsedMs: 0 };
    report.steps.push(entry);
    try { await run(); remaining(1); entry.passed = true; }
    finally { entry.elapsedMs = Date.now() - started - entry.startedMs; }
  }
  async function launch() {
    spawnError = undefined;
    const env = { ...process.env, PATH: `${process.env.SystemRoot}\\System32`, PYTHONPATH: '', PYTHONHOME: '',
      USERPROFILE: profile, HOMEDRIVE: parse(profile).root.replace(/[\\/]+$/, ''), HOMEPATH: profile.slice(parse(profile).root.length - 1),
      APPDATA: join(profile, 'AppData/Roaming'), LOCALAPPDATA: join(profile, 'AppData/Local'), TEMP: join(profile, 'Temp'), TMP: join(profile, 'Temp'),
      WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS: '', WEBVIEW2_USER_DATA_FOLDER: join(profile, 'AppData/Local/WebView2'), WEBVIEW2_BROWSER_EXECUTABLE_FOLDER: '' };
    // This is the visible GUI under test: Windows STARTUPINFO from windowsHide:true
    // hides MoMA's first window, so UIA cannot exercise the production interface.
    // Noninteractive PowerShell helpers above remain hidden.
    child = spawn(join(packaged, 'MoMA-Web.exe'), [], { cwd: packaged, windowsHide: false, env });
    child.on('error', error => { spawnError = error; });
    child.stdout?.on('data', value => { output += value; }); child.stderr?.on('data', value => { output += value; });
    report.launches.push({ pid: child.pid, executable: child.spawnfile, utc: new Date().toISOString() });
    if (!child.pid) throw new Error('正式包未创建 launcher PID');
    await owned('sample', child.pid);
    await native('read', '打开工程', 'Button');
  }
  async function openProject() {
    await native('click', '打开工程', 'Button'); await native('dialog', '选择文件夹', '', project);
    await native('expandTree', '工程文件', 'Tree');
    await native('read', '包装单元', 'TreeItem');
  }
  async function health(expected: number) {
    await expect.poll(async () => (await native('read', '生命值', 'Edit')).target?.value,
      { timeout: remaining(18_000), intervals: [200] }).toBe(String(expected));
  }
  async function closeProject() {
    // UIA locates the hit-tested native mouse click; no activation is replayed.
    // The following independent welcome-state assertion proves closure.
    await native('click', '文件', 'Button');
    await native('click', '关闭工程', 'MenuItem');
    await native('read', '尚未打开工程', 'Text');
  }
  async function closeNormally(cleanup = false) {
    if (!child) return;
    await native('close', '', '', '', cleanup);
    await expect.poll(async () => {
      const data = await owned('check', undefined, cleanup);
      return { exited: child!.exitCode === 0 && child!.signalCode === null, survivors: data.survivors?.length };
    }, { timeout: remaining(16_000, cleanup), intervals: [300] }).toEqual({ exited: true, survivors: 0 });
    report.launches.at(-1).exit = { code: child.exitCode, signal: child.signalCode, allSampledIdentitiesExited: true };
    child = undefined;
  }
  try {
    await step('准备隔离用户与中文路径目录包', async () => {
      await cp(source, packaged, { recursive: true, errorOnExist: true, force: false });
      for (const directory of ['AppData/Roaming/MoMA', 'AppData/Local', 'Temp']) await mkdir(join(profile, directory), { recursive: true });
      for (const directory of ['content/units', 'content/blocks']) await mkdir(join(project, directory), { recursive: true });
      await writeFile(join(profile, 'AppData/Roaming/MoMA/settings.json'), JSON.stringify({ display_name_mode: 'zh', auto_save_interval: 0 }));
      await writeFile(join(project, 'mod.json'), JSON.stringify({ name: 'package-native', displayName: '原生包装验收', version: '1.0', author: '自动化验收', minGameVersion: '159' }));
      await writeFile(join(project, 'content/units/package-unit.json'), JSON.stringify({ type: 'flying', name: '包装单元', health: 137 }));
      await writeFile(join(project, 'content/blocks/package-wall.json'), JSON.stringify({ type: 'Wall', name: '包装方块', health: 823, size: 1, requirements: [] }));
      await writeFile(png, Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64'));
      report.exeSha256 = createHash('sha256').update(await readFile(join(packaged, 'MoMA-Web.exe'))).digest('hex');
      report.testSha256 = createHash('sha256').update(await readFile(import.meta.filename)).digest('hex');
      report.helperSha256 = createHash('sha256').update(await readFile(resolve(import.meta.dirname, 'package-native.ps1'))).digest('hex');
    });
    await step('正式无调试启动与关于实际版本', async () => {
      await launch(); await native('click', '关于', 'Button');
      const about = await native('dump');
      const product = await readFile(join(root, 'pyproject.toml'), 'utf8');
      const version = product.match(/^version\s*=\s*"([^"]+)"/m)?.[1];
      if (!version) throw new Error('无法读取当前产品版本用于独立核对');
      const metadata = JSON.parse(await readFile(join(root, 'metadata/manifest.json'), 'utf8'));
      const names = ((about.elements ?? []) as { name: string }[]).map(item => item.name);
      expect(names).toContain(version); expect(names).toContain('产品版本'); expect(names).toContain('目标游戏版本');
      expect(names).toContain(metadata.gameVersion);
      report.about = { version, gameVersion: metadata.gameVersion, dump: about };
      await native('click', '关闭', 'Button');
    });
    await step('UI新建独立工程并正常关闭后打开双内容磁盘fixture', async () => {
      await native('click', '新建工程', 'Button');
      await native('setValue', '模组 ID', 'Edit', 'package-created');
      await native('setValue', '显示名称', 'Edit', '原生新建验收');
      await native('setValue', '作者', 'Edit', '自动化验收');
      // Re-read after all three entries so a later focus/change cannot silently
      // erase an earlier field; SetValue readback alone is not business acceptance.
      for (const [name, value] of [['模组 ID', 'package-created'], ['显示名称', '原生新建验收'], ['作者', '自动化验收']]) {
        expect((await native('read', name, 'Edit')).target?.value, name).toBe(value);
      }
      await native('click', '选择父目录并创建', 'Button');
      await native('dialog', '选择文件夹', '', temporary);
      await expect.poll(() => readFile(join(createdProject, 'mod.json'), 'utf8').then(JSON.parse).catch(() => null),
        { timeout: remaining(8_000) }).toMatchObject({ name: 'package-created', displayName: '原生新建验收', author: '自动化验收' });
      report.createdProject = { path: createdProject, mod: JSON.parse(await readFile(join(createdProject, 'mod.json'), 'utf8')) };
      await closeProject(); await openProject();
    });
    await step('两个内容独立编辑并验证撤销重做', async () => {
      await native('click', '包装单元', 'TreeItem'); await health(137);
      await native('setNumericValue', '生命值', 'Edit', '437'); await health(437);
      await native('click', '包装方块', 'TreeItem'); await health(823);
      await native('setNumericValue', '生命值', 'Edit', '654'); await health(654);
      await native('click', '撤销', 'Button'); await health(823);
      await native('click', '重做', 'Button'); await health(654);
      await native('click', '包装单元', 'TreeItem'); await health(437);
    });
    await step('保存双内容并独立读回磁盘', async () => {
      await native('click', '保存已打开内容', 'Button');
      await expect.poll(async () => JSON.parse(await readFile(join(project, 'content/units/package-unit.json'), 'utf8')).health,
        { timeout: remaining(8_000) }).toBe(437);
      expect(JSON.parse(await readFile(join(project, 'content/blocks/package-wall.json'), 'utf8')).health).toBe(654);
      report.saved = { unitHealth: 437, wallHealth: 654 };
    });
    await step('UIA显式源码填值保留未知结构并保存读回', async () => {
      await native('click', 'JSON 源码', 'Button');
      const sourceData = { type: 'flying', name: '包装单元', health: 437, packageUnknown: { kept: true, values: [1, 'literal{+^%}', 3] } };
      await native('setValue', 'JSON 源码', 'Edit', JSON.stringify(sourceData));
      // A real button invocation changes focus; the source's blur/explicit save flushes its draft.
      await native('click', '保存已打开内容', 'Button');
      await expect.poll(() => readFile(join(project, 'content/units/package-unit.json'), 'utf8').then(JSON.parse),
        { timeout: remaining(8_000) }).toEqual(sourceData);
      report.sourceRoundTrip = sourceData;
      await native('click', '表单', 'Button'); await health(437);
    });
    await step('原生PNG导入与真实磁盘撤销重做', async () => {
      await native('reveal', '导入主体贴图', 'Button');
      await native('click', '导入主体贴图', 'Button'); await native('dialog', '打开', '', png);
      const expected = await readFile(png);
      await expect.poll(() => readFile(sprite).catch(() => null), { timeout: remaining(8_000) }).toEqual(expected);
      await native('click', '撤销', 'Button');
      await expect.poll(() => stat(sprite).then(() => true).catch(error => { if (error.code === 'ENOENT') return false; throw error; }),
        { timeout: remaining(8_000) }).toBe(false);
      await native('click', '重做', 'Button');
      await expect.poll(() => readFile(sprite).catch(() => null), { timeout: remaining(8_000) }).toEqual(expected);
      report.sprite = { path: sprite, sha256: createHash('sha256').update(expected).digest('hex'), undoneAbsent: true, redoneIdentical: true };
    });
    await step('真实保存拒绝后保留修改并恢复重试', async () => {
      await native('setNumericValue', '生命值', 'Edit', '438'); await health(438);
      const file = join(project, 'content/units/package-unit.json'), backup = join(project, 'content/units/package-unit-held.json');
      await rename(file, backup); let obstructionCreated = false;
      try {
        await mkdir(file); obstructionCreated = true;
        await native('click', '保存已打开内容', 'Button');
        const diagnostic = await native('read', '保存失败，修改仍保留，请检查文件占用和访问权限后重试。', 'Text');
        await health(438);
        expect(JSON.parse(await readFile(backup, 'utf8')).health).toBe(437);
        report.saveFailure = { diagnostic, inputRetained: 438, diskRetained: 437 };
      } finally {
        // The only deletion is this test-created empty directory, never a recursive project deletion.
        if (obstructionCreated) await rmdir(file);
        await rename(backup, file);
      }
      await native('click', '保存已打开内容', 'Button');
      await expect.poll(() => readFile(file, 'utf8').then(JSON.parse).then(data => data.health),
        { timeout: remaining(8_000) }).toBe(438);
      report.saved.unitHealth = 438;
    });
    await step('原生导出并逐成员核对 ZIP 与磁盘', async () => {
      await native('click', '导出模组', 'Button'); await native('dialog', '另存为', '', exported);
      await expect.poll(() => readFile(exported).then(value => value.length).catch(() => 0), { timeout: remaining(8_000) }).toBeGreaterThan(0);
      const buffer = await readFile(exported);
      // Central directory offsets support ZIP writers that use data descriptors.
      let end = buffer.length - 22;
      while (end >= Math.max(0, buffer.length - 65_557) && buffer.readUInt32LE(end) !== 0x06054b50) end--;
      if (end < 0 || buffer.readUInt32LE(end) !== 0x06054b50) throw new Error('ZIP 结束目录缺失');
      const count = buffer.readUInt16LE(end + 10); let offset = buffer.readUInt32LE(end + 16);
      const members: Record<string, string> = {};
      for (let index = 0; index < count; index++) {
        expect(buffer.readUInt32LE(offset)).toBe(0x02014b50);
        const size = buffer.readUInt32LE(offset + 20), plainSize = buffer.readUInt32LE(offset + 24);
        const nameLength = buffer.readUInt16LE(offset + 28), extra = buffer.readUInt16LE(offset + 30), comment = buffer.readUInt16LE(offset + 32);
        const name = buffer.subarray(offset + 46, offset + 46 + nameLength).toString('utf8');
        if (name.startsWith('/') || name.includes('..') || name.includes('\\') || Object.hasOwn(members, name)) throw new Error('ZIP 包含不安全或重复成员');
        const local = buffer.readUInt32LE(offset + 42), method = buffer.readUInt16LE(offset + 10);
        expect(buffer.readUInt32LE(local)).toBe(0x04034b50);
        const dataStart = local + 30 + buffer.readUInt16LE(local + 26) + buffer.readUInt16LE(local + 28);
        const compressed = buffer.subarray(dataStart, dataStart + size);
        if (![0, 8].includes(method)) throw new Error('验收执行器不支持此 ZIP 压缩方法');
        const data = method === 8 ? inflateRawSync(compressed) : compressed;
        expect(data.length).toBe(plainSize);
        if (!name.endsWith('/')) expect(data.equals(await readFile(join(project, name))), name).toBe(true);
        members[name] = createHash('sha256').update(data).digest('hex'); offset += 46 + nameLength + extra + comment;
      }
      for (const required of ['mod.json', 'content/units/package-unit.json', 'content/blocks/package-wall.json', 'sprites/units/package-unit.png']) expect(Object.hasOwn(members, required)).toBe(true);
      report.export = { sha256: createHash('sha256').update(buffer).digest('hex'), members };
      await info.attach('正式包原生导出ZIP', { path: exported, contentType: 'application/zip' });
    });
    await step('同一正式宿主关闭工程再重开保存结果', async () => {
      const launcher = child?.pid;
      await closeProject(); await openProject();
      await native('click', '包装单元', 'TreeItem'); await health(438);
      await native('click', '包装方块', 'TreeItem'); await health(654);
      expect(child?.pid).toBe(launcher);
      expect(child?.exitCode).toBe(null);
      report.sameHostReopen = { pid: launcher, unitHealth: 438, wallHealth: 654 };
    });
    await step('正常关闭释放后重启并读回保存结果', async () => {
      await closeNormally(); await launch(); await openProject();
      await native('click', '包装单元', 'TreeItem'); await health(438);
      await native('click', '包装方块', 'TreeItem'); await health(654);
      await native('dump'); await closeNormally();
    });
    report.pass = true;
  } catch (error) {
    report.error = String(error);
    try { await native('dump', '', '', '', true); } catch (dumpError) { report.dumpError = String(dumpError); }
    throw error;
  } finally {
    if (child) {
      try { await closeNormally(true); } catch (error) { report.cleanupErrors.push(String(error)); }
      try {
        const status = await owned('check', undefined, true, true);
        if (status.survivors?.length) {
          report.forcedTermination = true; await owned('terminate', undefined, true, true);
          const final = await owned('check', undefined, true, true); report.survivors = final.survivors;
          if (final.survivors?.length) report.cleanupErrors.push('精确身份清理后仍有本次进程存活');
        }
      } catch (error) { report.cleanupErrors.push(String(error)); }
    }
    report.elapsedMs = Date.now() - started;
    report.pass = report.pass && !report.forcedTermination && report.cleanupErrors.length === 0 && report.elapsedMs < 300_000;
    // Preserve isolated user logs and fixture files for inspection, especially on failure.
    await writeFile(info.outputPath('正式包原生验收结果.json'), JSON.stringify(report, null, 2));
    await info.attach('正式包原生验收结果', { body: JSON.stringify(report, null, 2), contentType: 'application/json' });
    await info.attach('正式包标准输出', { body: output || '进程未写标准输出；隔离用户日志保留于 fixture 目录', contentType: 'text/plain' });
    if (info.status === 'passed') expect(report.pass, JSON.stringify(report)).toBe(true);
  }
});
