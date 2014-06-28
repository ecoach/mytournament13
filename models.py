from django.db import models
from django.db.models import Max
from django.db.models import F, Q
from datetime import datetime
import json

# Create your models here.

class Bracket(models.Model):
    class Meta: 
        db_table = 'mytournament_bracket'
    # [12m_Competitor]
    # [12m_Judge]
    # [12m_Bout]
    name = models.CharField(max_length=30, null=True, blank=True)
    description = models.CharField(max_length=100, null=True, blank=True)
    manager = models.CharField(max_length=30, null=True, blank=True)
    ready = models.NullBooleanField()
    finished = models.NullBooleanField()

    def get_bout(self, judge):
        pass
        # check if judge is eligable to make decisions
        # return choices 
        # use manager to decide next set of bouts
        # eval(self.manager).repair()

class Competitor(models.Model):
    class Meta: 
        db_table = 'mytournament_competitor'
    # [12m_Bout]
    bracket = models.ForeignKey(Bracket)
    name = models.CharField(max_length=30, null=True, blank=True)
    game = models.TextField(null=True, blank=True)
    beat = models.TextField(null=True, blank=True)      # json array of who they beat
    beatby = models.TextField(null=True, blank=True)    # json array of who beat them
    wins = models.IntegerField(null=True, blank=True)
    losses = models.IntegerField(null=True, blank=True)
    draws = models.IntegerField(null=True, blank=True)
    byes = models.IntegerField(null=True, blank=True)
    points = models.IntegerField(null=True, blank=True)
    status = models.IntegerField(null=True, blank=True)

    def Get_Beatby(self):
        try: 
            ret = json.loads(self.beatby)
            if isinstance(ret, list):
                return ret
        except:
            pass
        return []

        
    def Get_Beat(self):
        try: 
            ret = json.loads(self.beat)
            if isinstance(ret, list):
                return ret
        except:
            pass
        return []

    def Set_Beatby(self, beatby):
        self.beatby = json.dumps(beatby)
        self.save()
   
    def Set_Beat(self, beat):
        self.beat = json.dumps(beat)
        self.save()

    def Add_Beat(self, who):
        beat = self.Get_Beat() 
        beat.append(who)
        self.Set_Beat(beat)
     
    def Add_Beatby(self, who):
        beatby = self.Get_Beatby() 
        beatby.append(who)
        self.Set_Beatby(beatby)
    
class Judge(models.Model):
    class Meta: 
        db_table = 'mytournament_judge'
    # [12m_Bout]
    bracket = models.ForeignKey(Bracket)
    name = models.CharField(max_length=30, null=True, blank=True)
    eligable = models.IntegerField(null=True, blank=True)
    decisions = models.IntegerField(null=True, blank=True)

class Bout(models.Model):
    class Meta: 
        db_table = 'mytournament_bout'
    bracket = models.ForeignKey(Bracket)
    bround = models.IntegerField(null=True, blank=True)
    judge = models.ForeignKey(Judge, null=True)
    compA = models.ForeignKey(Competitor, related_name='compA')
    compB = models.ForeignKey(Competitor, related_name='compB')
    winner = models.ForeignKey(Competitor, related_name='winner', null=True)
    btime = models.DateTimeField(null=True, blank=True)


class Base_Tourney(object):

    def __init__(self, bracket):
        self.bracket = bracket

    def Register(self, name, game):
        if not self.bracket.ready:
            cc = Competitor.objects.get_or_create(bracket=self.bracket, name=name)[0]
            cc.game = game
            cc.wins = 0
            cc.losses = 0
            cc.points = 0
            cc.byes = 0
            cc.status = -1
            cc.save()

    def Game(self, competitor):
        try:  
            return Competitor.objects.get(bracket=self.bracket, name=competitor.username).game
        except:
            return ""

    def Setup(self, who):
        # cascade events
        self.Round_Cleanup() 
        if self.bracket.finished:
            return
        judge = self.Get_Judge(who)
        if self.Round_Complete(judge):
            self.Advancing()
            self.RePair()

    def Votes_Remaining_Judge(self, who):
        return self.bracket.judge_set.filter(eligable__gt=F('decisions'), name=who)

    def Decisions_Remaining_Bracket(self):
        return self.bracket.judge_set.filter(eligable__gt=F('decisions'))
        #judgements = judgements.filter(~Q(name=who))
    
    def Get_Judge(self, who):
        # get judge object for voter
        try:
            judge = Judge.objects.get(bracket=self.bracket, name=who)
            return judge
        except:
            return False

    def Round_Cleanup(self):
        # if judges havent' been loaded yet don't clean up and set to finished
        if len(self.bracket.judge_set.all()) == 0:
            return          
        # if there aren't any judgements left we're done (plus clean up party trash)
        if len(self.Decisions_Remaining_Bracket()) == 0  or self.bracket.finished == 1:
            # bracket can finish for other reasons...in which case cleanup can still happen
            self.bracket.finished = 1
            self.bracket.save()
            # find all the dangling bouts (party trash) and delete them
            Bout.objects.filter(bracket=self.bracket, winner__isnull=True).delete()
            return 

        # remove dangling vote assignments
        # look up all active vote assignments for this bracket
        # spin over and clear any that are older than 15 minutes
        dangling = Bout.objects.filter(bracket=self.bracket, winner__isnull=True, btime__isnull=False)
        for bb in dangling:
            del_minutes = (datetime.now() - bb.btime).seconds / 60
            if del_minutes >= 15:
                #bb.delete()
                bb.judge = None
                bb.btime = None
                bb.save()

    def Round_Complete(self, judge):
        # check if there are any bouts remaining in current/last round
        all_rounds = self.bracket.bout_set.all()
        if len(all_rounds) == 0:
            return True
        last_round = all_rounds.aggregate(Max('bround'))
        current_round = last_round['bround__max']
        remain = all_rounds.filter(bround=current_round, winner__isnull=True)
        #remain = all_rounds.filter(~Q(judge=judge), bround=current_round, winner__isnull=True)
        return (len(remain) == 0)

    def RePair(self):
        pass

    def Advancing(self):
        # only winners advance in single elimination
        pass 

    def Get_Next_Round_Number(self):
        # assumes last round is complete 
        all_rounds = self.bracket.bout_set.all()
        # no bouts yet means first round
        if len(all_rounds) == 0:
            return 1
        last_round = all_rounds.aggregate(Max('bround'))
        return (last_round['bround__max'] + 1)

    def Status(self, who):
        if self.bracket.finished: # everyone can see once it's done
            return "MESSAGE_WINNER" 
        if not self.Status_Participating(who):
            return "MESSAGE_NON_PART"
        elif self.Status_Wait(who):
            return "MESSAGE_WAIT"
        elif self.Status_Vote_Ready(who):
            return "MESSAGE_VOTE"
        elif self.Status_Vote_Done(who): 
            return "MESSAGE_THANKS"
        else:
            return "MESSAGE_WINNER"

    def GetWinner(self):
        # this should maybe print the ordering results...
        comps = self.bracket.competitor_set.filter(status=0).extra(select={'rank': 'wins - losses'}).order_by('-rank')
        winners = []
        for cc in comps:
            winners.append([cc.wins, cc.losses, cc.game]) 
        return winners

    def Status_Participating(self, who):
        # check if you're assigned to vote in this bracket
        judge = self.Get_Judge(who)
        if not judge:
            return False
        return True 

    def Status_Wait(self, who):
        # check if the voting assignments are all distributed for this round 
        # should already know they are a judge (they would have got non-part msg)
        # this depends on cleanup running first...
        if self.bracket.finished == 1:
            return False
        if self.Decisions_Remaining_Bracket() == 0:
            return False
        if len(self.Votes_Remaining_Judge(who)) == 0:
            return False
        if not self.Bout_Assignment(who): # this being third requires above both false
            return True
        return False

    def Status_Vote_Ready(self, who):
        # make sure they have a bout assigned and there's not already a winner
        return self.Bout_Assignment(who)

    def Status_Vote_Done(self, who):
        if self.bracket.finished:
            return False
        return True
        pass

    def Vote_Choices(self, who):
        bout = self.Bout_Assignment(who)
        if not bout:
            return [('some_url', "<a href='" + 'some_url' + "'>if you get see this please report it...</a>"), 
                    ('another_url',"<a href='" + 'another_url' + "'>for some reason bout not ready for this bracket!</a>")] 
        return [(bout.compA.game, "<a href='" + bout.compA.game + "' class='data-log-external' target='_blank'>submission 1 (click to review " + bout.compA.game + ")</a>"), 
                    (bout.compB.game,"<a href='" + bout.compB.game + "' class='data-log-external' target='_blank'>submission 2 (click to review " + bout.compB.game + ")</a>")] 

       
    def Bout_Assignment(self, who):
        # make sure they have votes left
        dec = self.Votes_Remaining_Judge(who)
        if len(dec) == 0:
            return False
        judge = dec[0] 
        # check if bout assignment already exists
        on_deck = self.bracket.bout_set.filter(judge=judge, winner__isnull=True)
        if len(on_deck) > 0:
            return on_deck[0]
        # or try to make a new bout assignment 
        in_hole = self.bracket.bout_set.filter(judge__isnull=True, winner__isnull=True)
        for bout in in_hole:
            # don't assign someone their own stuff to judge!
            if bout.compA.name != who and bout.compB.name != who:
                bout.judge = judge
                bout.btime = datetime.now()
                bout.save()
                return bout
        return False

    def Bout_Id(self, who):
        bout = self.Bout_Assignment(who)
        if not bout:
            return 0
        return bout.id

    def Record_Vote(self, bout_id, who, game):
        try:
            # make sure the vote is still assigned to them, may have timed out!
            bout = Bout.objects.get(id=bout_id)
            winner = Competitor.objects.get(bracket=self.bracket, game=game)
            judge = Judge.objects.get(bracket=self.bracket, name=who)
        except: 
            # must have timed out!
            return
        if winner == bout.compA:
            looser = bout.compB
        else:
            looser = bout.compA
        # set record the competitors stats
        judge.decisions += 1
        judge.save()
        looser.losses += 1
        looser.Add_Beatby(winner.name)
        looser.save()
        winner.wins += 1 
        winner.Add_Beat(looser.name)
        winner.save()
        # record the bout winner
        bout.winner = winner
        bout.save()

class Single_Elimination(Base_Tourney):

    def __init__(self, **kwargs):
        super(Single_Elimination, self).__init__(**kwargs)

    def RePair(self):
        bround = self.Get_Next_Round_Number()
        comp_res = Competitor.objects.filter(bracket=self.bracket, losses=0, status=0).extra(order_by = ['byes'])
        competitors = [x for x in comp_res]
        # check if a winner has already been found...
        if len(competitors) == 1:
            # this only needs to happen once...competitors may loose in negative rounds...no matter
            winner = competitors[0]
            winner.save()
            # check if judgements remain and retrace or declare a winner
            judgements = self.Decisions_Remaining_Bracket()
            # works in single elimination 
            # this creates party trash when the last person to vote submits...extra bout
            repeats = Bout.objects.filter(winner=winner, judge__isnull=False).order_by('btime')
            for ii in range(0, len(judgements)):
                bout = Bout(bracket=self.bracket, bround=-repeats[ii].bround, judge=None, compA=repeats[ii].compA, compB=repeats[ii].compB)
                bout.save() 
            return
        # handle the bye
        if len(competitors) % 2 > 0:
            bye = competitors[0]
            competitors = competitors[1:]
            btime = datetime.now()
            bout = Bout(bracket=self.bracket, bround=bround, judge=None, compA=bye, compB=bye, winner=bye, btime=btime)
            bout.save()
            bye.byes += 1
            bye.wins += 1
            bye.save()
        comps = []
        while(len(competitors) > 1):
            one = competitors.pop()
            two = competitors.pop()
            comps.append([one,two])
        for cc in comps:
            bout = Bout(bracket=self.bracket, bround=bround, judge=None, compA=cc[0], compB=cc[1])
            bout.save() 

class Absolute_Order(Base_Tourney):

    def __init__(self, **kwargs):
        super(Absolute_Order, self).__init__(**kwargs)

    def Advancing(self):
        # everyone advances
        pass

    def RePair(self):
        if len(self.Decisions_Remaining_Bracket()) == 0:
            return
        bround = self.Get_Next_Round_Number()
        comp_res = Competitor.objects.filter(bracket=self.bracket, status=0)
        competitors = [x for x in comp_res]
        # make groups of competitors
        comp_groups = dict()
        win_set_size = len(set([x.wins for x in self.bracket.competitor_set.filter(status=0)]))
        comp_set_size = len(self.bracket.competitor_set.filter(status=0))
        match_losses = False
        if win_set_size == comp_set_size:
            match_losses = True
        for cc in competitors:
            gparam = cc.wins
            if match_losses:
                gparam = cc.losses
            #gparam = cc.wins - cc.losses
            #gparam = round(float(cc.losses) / (cc.wins + 1), 1)
            if not gparam in comp_groups.keys():
                comp_groups[gparam] = []
            comp_groups[gparam].append(cc)
        cgroups = []
        keys = sorted(comp_groups.keys(), reverse=True)
        for gg in keys:
            cgroups.append(comp_groups[gg])
        useful=0
        for gg in cgroups:  
            useful += self.CreateRound(gg, bround)
        # when no bouts are found at all things are done
        if useful == 0:
            self.bracket.finished = 1
            self.bracket.save()
 
    def CreateRound(self, comps, rnd):
        bouts = [] # list of bouts in that round
        comps.sort(key=lambda x: (x.wins - x.losses), reverse=True) 
        byes_tally = []
        #decisions_remaining = sum([x.eligable - x.decisions for x in self.Decisions_Remaining_Bracket()])
        # this does fold the sorted list :)
        while(len(comps) > 0):
        #while(len(comps) > 0 and decisions_remaining > 0):
            one = comps.pop()
            one.byes += 1
            one.save()
            byes_tally.append(one)
            for two in comps:
                two.Get_Beat()
                if not one.name in (two.Get_Beat() + two.Get_Beatby()):
                    one.byes -= 1
                    one.save()
                    byes_tally.pop()
                    bouts.append([one,two]) 
                    comps.remove(two)
                    #decisions_remaining -= 1
                    break
        if len(bouts) < 1:
            return 0
        for cc in bouts:
            bout = Bout(bracket=self.bracket, bround=rnd, judge=None, compA=cc[0], compB=cc[1])
            bout.save()
        return 1
 
class Top(Base_Tourney):
    seeking = 3

    def __init__(self, **kwargs):
        super(Top, self).__init__(**kwargs)

    def Advancing(self):
        # decide if selection or elimination round
        # find everyone who is advancing to the next round
        # set status of those selected/eliminated
        pass 


class Top20(Top):
    seeking = 3

    def __init__(self, **kwargs):
        super(Top20, self).__init__(**kwargs)

class Top10(Top):
    seeking = 10

    def __init__(self, **kwargs):
        pass

class Genetic(Base_Tourney):

    def __init__(self, **kwargs):
        pass

class Swiss_Style(Base_Tourney):

    def __init__(self, **kwargs):
        pass




