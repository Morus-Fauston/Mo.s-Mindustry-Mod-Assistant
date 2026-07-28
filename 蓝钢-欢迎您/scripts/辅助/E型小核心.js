const 临时核心 = extend(CoreBlock, "临时核心", {
    
    canBreak() { return Vars.state.teams.cores(Vars.player.team()).size > 1; },
    canReplace(other) { return other.alwaysReplace; },
    canPlaceOn(tile, team) { return true; },
    
    
});
exports.临时核心 = 临时核心;